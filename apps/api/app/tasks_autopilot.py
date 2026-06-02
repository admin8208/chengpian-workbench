import json
import shutil
from datetime import datetime
from pathlib import Path
import re

from loguru import logger
from sqlmodel import select

from app.compliance import check_text
from app.audio_input import transcribe_audio_to_segments
from app.db import session_scope
from app.jobs import get_job_payload, patch_job_payload, update_job, wait_if_job_paused
from app.llm_client import LlmError
from app.models import Asset, ChannelPack, Job, LlmProvider, Project, Scene
from app.modules.pipeline.orchestrator import run_pipeline_job
from app.modules.pipeline.state import normalize_autopilot_stage, project_has_confirmed_baseline
from app.modules.storyboard.service import save_storyboard
from app.modules.visual.resolver import resolve_visual_pipeline
from app.image_service import get_default_image_provider, get_image_api_key
from app.modules.tts.service import get_default_voice_rate, get_edge_voice_id, tts_status_dict
from app.material_policies import project_material_mode
from app.project_paths import asset_disk_path, project_audio_dir, project_exports_dir, project_subtitles_dir, rel_to_projects_root
from app.settings import settings
from app.subtitles import clean_tts_text
from app.storyboard_postprocess import enrich_storyboard_continuity, search_en_from_visual_intent
from app.prompts import track_query_bias
from app.scene_semantics import infer_scene_semantics, scene_negative_from_semantics, scene_prompt_from_semantics
from app.tasks_render_bridge import stable_digest_bridge
from app.tasks_render_prepare import prepare_render_context
from app.tasks_tts_cache import build_generated_tts_cache_paths
from app.time_utils import now_utc


AUTOPILOT_STAGES = ("storyboard", "media", "tts", "render")


def project_input_mode(project: Project | None) -> str:
    cfg = project.render_config() if project and hasattr(project, "render_config") else {}
    mode = str((cfg or {}).get("input_mode") or "text").strip().lower()
    return "audio" if mode == "audio" else "text"


def _derive_media_query(text: str) -> str:
    clean = re.sub(r"\s+", " ", str(text or "").strip())
    clean = clean.replace("，", " ").replace("。", " ").replace("！", " ").replace("？", " ")
    return clean[:120].strip()


def _scene_prompt_from_visual(*, idx: int, style: str, narration: str, visual: dict | None, aspect: str = "landscape") -> str:
    vi = visual if isinstance(visual, dict) else {}
    subject = str(vi.get("subject") or "真实人物").strip()
    action = str(vi.get("action") or narration or "处在一个具体情境中").strip()
    setting = str(vi.get("setting") or "真实场景").strip()
    time_of_day = str(vi.get("time") or "自然光环境").strip()
    shot = str(vi.get("shot") or "medium cinematic shot").strip()
    frame_ratio = "vertical 9:16" if str(aspect or "").strip().lower() == "portrait" else "horizontal 16:9"
    frame_guidance = "tall cinematic framing with safe top and bottom margins" if frame_ratio == "vertical 9:16" else "wide cinematic framing with safe side margins"
    return ", ".join(
        [
            "photorealistic",
            "Chinese cinematic realism",
            style,
            frame_ratio,
            f"scene {idx}",
            subject,
            action,
            setting,
            time_of_day,
            shot,
            "natural lighting",
            "real human emotion",
            frame_guidance,
            "realistic",
        ]
    )


def _split_confirmed_script(script: str, *, max_segments: int) -> list[str]:
    text = clean_tts_text(script)
    if not text:
        return []
    parts = [p.strip() for p in re.split(r"(?<=[。！？!?])", text) if p.strip()]
    if not parts:
        parts = [text]
    target = max(1, int(max_segments or 8))
    if len(parts) <= target:
        return parts
    total_chars = max(1, sum(len(p) for p in parts))
    target_chars = max(30, int(total_chars / target))
    segments: list[str] = []
    buf = ""
    for part in parts:
        candidate = f"{buf}{part}" if buf else part
        if buf and len(candidate) >= target_chars and len(segments) < target - 1:
            segments.append(candidate.strip())
            buf = ""
        else:
            buf = candidate
    if buf.strip():
        segments.append(buf.strip())
    while len(segments) > target:
        tail = segments.pop()
        segments[-1] = f"{segments[-1]}{tail}"
    return [s for s in segments if s]


def build_confirmed_script_storyboard(script: str, *, pack: ChannelPack, render_cfg: dict | None, material_mode: str) -> tuple[str, list[dict]]:
    fixed_script = clean_tts_text(script)
    if not fixed_script:
        raise LlmError("confirmed script empty")
    try:
        cfg = pack.config()
    except Exception:
        cfg = {}
    try:
        scene_count = int((render_cfg or {}).get("scene_count") or cfg.get("scene_count") or 8)
    except Exception:
        scene_count = 8
    scene_count = max(1, min(12, scene_count))
    try:
        base_dur = float((render_cfg or {}).get("scene_duration_sec") or cfg.get("scene_duration_sec") or 6.0)
    except Exception:
        base_dur = 6.0
    base_dur = max(2.0, min(15.0, base_dur))

    pack_key = str(getattr(pack, "key", "") or "").strip().lower()
    mode = str(material_mode or "network").strip().lower() or "network"
    aspect = str((render_cfg or {}).get("aspect") or "landscape").strip().lower() or "landscape"
    bias = track_query_bias(pack_key)
    style = str(cfg.get("style", "cinematic realism") if isinstance(cfg, dict) else "cinematic realism")
    negative = str(cfg.get("negative", "") if isinstance(cfg, dict) else "")
    segments = _split_confirmed_script(fixed_script, max_segments=scene_count)
    if not segments:
        segments = [fixed_script]
    scenes: list[dict] = []
    for idx, narration in enumerate(segments, start=1):
        visual = infer_scene_semantics(narration=narration, pack_key=pack_key, visual_hint=None)
        media_query = _derive_media_query(narration)
        search_en = search_en_from_visual_intent(visual, bias)
        image_prompt = ""
        if mode == "ai":
            image_prompt = scene_prompt_from_semantics(idx=idx, style=style, narration=narration, semantics=visual, aspect=aspect)
        meta = {
            "intent": {"pack_key": pack_key},
            "screen": {"text": ""},
            "visual": visual,
            "search": {"en": search_en, "anchor_query_en": search_en, "material_mode": mode},
            "story": {"template_stage": "", "scene_group": 0, "transition_hint": "continue"},
            "pack_key": pack_key,
            "prompt": {"workflow": str(render_cfg.get("workflow") if isinstance(render_cfg, dict) else "mix"), "writer": "confirmed_script_strict", "material_mode": mode},
            "strict_confirmed_script": True,
        }
        scenes.append(
            {
                "idx": idx,
                "narration": narration,
                "media_query": media_query,
                "image_prompt": image_prompt,
                "image_negative": ", ".join([x for x in [negative, scene_negative_from_semantics(visual)] if x]).strip(", "),
                "duration_sec": base_dur,
                "meta": meta,
            }
        )
    return fixed_script, enrich_storyboard_continuity(scenes)


def build_audio_storyboard(pid: int, *, audio_asset: Asset, title: str) -> tuple[str, list[dict]]:
    audio_path = asset_disk_path(str(audio_asset.rel_path or ""), is_export=False)
    if not audio_path.exists() or not audio_path.is_file():
        raise RuntimeError("音频文件不存在，请重新上传后再试。")
    script = ""
    scenes: list[dict] = []
    audio_duration = 0.0
    try:
        result = transcribe_audio_to_segments(audio_path)
        script = str(result.full_text or "").strip()
        audio_duration = float(result.audio_duration or 0.0)
        for seg in result.segments:
            text = str(seg.text or "").strip()
            if not text:
                continue
            scenes.append(
                {
                    "idx": int(seg.idx),
                    "narration": text,
                    "media_query": _derive_media_query(text),
                    "image_prompt": "",
                    "image_negative": "",
                    "duration_sec": max(2.0, float(seg.duration_sec or 4.0)),
                    "meta": {
                        "audio_start_sec": float(seg.start_sec or 0.0),
                        "audio_end_sec": float(seg.end_sec or 0.0),
                        "audio_duration_sec": float(seg.duration_sec or 0.0),
                        "generated_from_audio": True,
                    },
                }
            )
    except Exception:
        script = ""
        scenes = []
    if not audio_duration:
        try:
            from moviepy import AudioFileClip
            with AudioFileClip(str(audio_path)) as clip:
                audio_duration = float(clip.duration or 0.0)
        except Exception:
            audio_duration = 0.0
    if not script:
        script = str(title or "音频驱动项目").strip() or "音频驱动项目"
    if not scenes:
        scenes = [
            {
                "idx": 1,
                "narration": script,
                "media_query": _derive_media_query(script),
                "image_prompt": "",
                "image_negative": "",
                "duration_sec": max(3.0, float(audio_duration or 6.0)),
                "meta": {
                    "audio_start_sec": 0.0,
                    "audio_end_sec": float(audio_duration or 6.0),
                    "audio_duration_sec": float(audio_duration or 6.0),
                    "generated_from_audio": True,
                    "fallback_from_audio": True,
                },
            }
        ]
    return script, scenes


def _audio_pipeline_preflight() -> tuple[bool, str]:
    try:
        import tempfile

        from app.ffmpeg_utils import ffmpeg_path, run_ffmpeg

        tmp_base = settings.data_dir / "tmp"
        tmp_base.mkdir(parents=True, exist_ok=True)

        for attempt in range(3):
            try:
                with tempfile.TemporaryDirectory(prefix="chengpian_tts_preflight_", dir=str(tmp_base)) as td:
                    base = Path(td)
                    src = base / "src.wav"
                    out = base / "out.wav"
                    run_ffmpeg(["-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono", "-t", "0.5", ffmpeg_path(src)], timeout_s=30)
                    run_ffmpeg(["-y", "-i", ffmpeg_path(src), "-ac", "1", "-ar", "22050", ffmpeg_path(out)], timeout_s=30)
                    if not out.exists() or out.stat().st_size <= 0:
                        logger.warning("audio preflight attempt {} output file missing or empty", attempt + 1)
                        continue
                    return (True, "")
            except Exception as e:
                logger.warning("audio preflight attempt {} failed: {}", attempt + 1, e)
                if attempt < 2:
                    import time
                    time.sleep(1)
                    continue
                raise
        return (False, "audio pipeline config error")
    except Exception as e:
        logger.error("audio preflight failed: {}", e)
        return (False, "audio pipeline config error")
def _edge_audio_pipeline_preflight() -> tuple[bool, str]:
    try:
        import tempfile

        from app.ffmpeg_utils import ffmpeg_path, run_ffmpeg

        with tempfile.TemporaryDirectory(prefix="chengpian_edge_preflight_") as td:
            base = Path(td)
            src = base / "src.wav"
            out = base / "out.wav"
            run_ffmpeg(["-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono", "-t", "0.5", ffmpeg_path(src)], timeout_s=20)
            run_ffmpeg(["-y", "-i", ffmpeg_path(src), "-ac", "1", "-ar", "22050", ffmpeg_path(out)], timeout_s=20)
            if not out.exists() or out.stat().st_size <= 0:
                return (False, "在线音频处理环境不可用，请检查 ffmpeg。")
        return (True, "")
    except Exception:
        return (False, "在线音频处理环境不可用，请检查 ffmpeg。")
def classify_llm_failure(exc: Exception) -> tuple[str, str]:
    msg = str(exc or "").strip()
    low = msg.lower()
    if not msg:
        return ("llm_request_failed", "大模型请求失败")
    if any(x in low for x in ("401", "unauthorized", "incorrect api key", "invalid api key", "authentication")):
        return ("llm_auth_failed", "大模型鉴权失败，请检查 API Key")
    if any(x in low for x in ("403", "forbidden", "permission denied")):
        return ("llm_permission_denied", "大模型账号无权限访问当前模型")
    if any(x in low for x in ("429", "rate limit", "too many requests", "quota", "insufficient_quota")):
        return ("llm_rate_limited", "大模型请求被限流或额度不足")
    if any(x in low for x in ("timeout", "timed out", "read timeout", "connect timeout")):
        return ("llm_timeout", "大模型请求超时")
    if any(x in low for x in ("connection refused", "failed to establish a new connection", "name or service not known", "nodename nor servname", "max retries exceeded", "temporary failure in name resolution")):
        return ("llm_network_failed", "大模型服务不可达，请检查 base_url 或网络")
    if any(x in msg for x in ("JSON 解析失败", "unexpected response", "response JSON is not an object")):
        return ("llm_bad_response", "大模型返回格式异常，无法生成分镜")
    return ("llm_request_failed", msg[:220])


def classify_tts_failure(detail: str) -> bool:
    low = str(detail or "").strip().lower()
    if not low:
        return False
    hints = (
        "tts",
        "配音",
        "字幕",
        "edge tts",
        "offline",
        "voice",
        "subtitle",
        "无法生成配音",
    )
    return any(x in low for x in hints)


def humanize_autopilot_detail(detail: str) -> str:
    raw = _repair_mojibake_text(str(detail or "").strip())
    low = raw.lower()
    if not raw:
        return "执行失败，请稍后重试。"
    if raw in ("cancelled", "__job_cancelled__"):
        return "任务已取消。"
    if raw == "project_missing":
        return "项目不存在。"
    if raw == "media_stage_interrupted":
        return "素材阶段被中断，请从素材阶段继续。"
    if raw in ("final_render_failed", "final_missing", "final_check_failed"):
        return "最终成片生成失败，请从渲染阶段继续。"
    if "unexpected keyword argument" in low or "got an unexpected keyword" in low or "typeerror" in low:
        return "内部流程参数错误，请更新后重试。"
    if "timeout" in low or "timed out" in low:
        return "服务处理超时，请稍后重试。"
    if "database is locked" in low:
        return "渲染阶段数据库繁忙，请稍后重试。"
    if any(x in low for x in ("connection refused", "max retries exceeded", "temporary failure", "dns", "ssl", "proxy", "network")):
        return "网络连接异常，请检查当前服务配置和网络后重试。"
    if classify_tts_failure(raw):
        return "配音或字幕生成失败，请检查配音设置后重试。"
    if any(x in low for x in ("llm", "openai", "unauthorized", "forbidden", "quota", "429")):
        _code, msg = classify_llm_failure(Exception(raw))
        return msg
    if any(x in raw for x in ("仍有", "项目不存在", "频道内容包不存在")):
        return raw
    if "final.mp4" in raw:
        return "最终成片生成失败，请从渲染阶段继续。"
    return raw[:220]


def _repair_mojibake_text(text: str) -> str:
    raw = str(text or "")
    if not raw:
        return ""
    if "�" not in raw:
        return raw
    for source_encoding in ("gbk", "utf-8"):
        try:
            repaired = raw.encode("latin1", errors="ignore").decode(source_encoding, errors="ignore").strip()
        except Exception:
            continue
        if repaired and repaired != raw and any("\u4e00" <= ch <= "\u9fff" for ch in repaired):
            return repaired
    return raw


def has_reusable_generated_tts(project_id: int) -> bool:
    try:
        audio_path, srt_path = expected_generated_tts_paths(int(project_id))
        if not audio_path or not srt_path:
            return False
        return bool(
            audio_path.exists()
            and audio_path.is_file()
            and audio_path.stat().st_size > 0
            and srt_path.exists()
            and srt_path.is_file()
            and srt_path.stat().st_size > 0
        )
    except Exception:
        return False


def has_reusable_primary_audio_timeline(project_id: int) -> bool:
    if has_reusable_generated_tts(project_id):
        return True
    try:
        with session_scope() as session:
            project = session.exec(select(Project).where(Project.id == int(project_id))).first()
            if not project:
                return False
            audio_paths: list[Path] = []
            subtitle_paths: list[Path] = []
            if getattr(project, "voice_asset_id", None):
                asset = session.exec(select(Asset).where(Asset.id == int(project.voice_asset_id or 0))).first()
                if asset:
                    audio_paths.append(asset_disk_path(str(asset.rel_path or ""), is_export=False))
            if getattr(project, "subtitle_asset_id", None):
                asset = session.exec(select(Asset).where(Asset.id == int(project.subtitle_asset_id or 0))).first()
                if asset:
                    subtitle_paths.append(asset_disk_path(str(asset.rel_path or ""), is_export=False))
            generated_assets = session.exec(
                select(Asset)
                .where(Asset.project_id == int(project_id))
                .where(Asset.tag.in_(["voice_generated", "subtitle_generated"]))
            ).all()
            for asset in generated_assets:
                path = asset_disk_path(str(asset.rel_path or ""), is_export=False)
                if str(asset.tag or "") == "voice_generated":
                    audio_paths.append(path)
                elif str(asset.tag or "") == "subtitle_generated":
                    subtitle_paths.append(path)

        def _has_file(paths: list[Path]) -> bool:
            for path in paths:
                try:
                    if path.exists() and path.is_file() and path.stat().st_size > 0:
                        return True
                except Exception:
                    continue
            return False

        return _has_file(audio_paths) and _has_file(subtitle_paths)
    except Exception:
        return False


def expected_generated_tts_paths(project_id: int) -> tuple[Path | None, Path | None]:
    try:
        with session_scope() as session:
            prep_ctx = prepare_render_context(
                session=session,
                project_id=int(project_id),
                target_job_id=0,
                rcfg_override=None,
                get_pack=get_pack,
                get_edge_voice_id=get_edge_voice_id,
                get_default_voice_rate=get_default_voice_rate,
            )
            if not prep_ctx:
                return (None, None)
            project = prep_ctx.project
            pid = prep_ctx.pid
            scenes = prep_ctx.scenes
            script_text = clean_tts_text((project.script or "").strip() or "\n".join([s.narration.strip() for s in scenes if s.narration.strip()]))
            if not script_text:
                return (None, None)
            _tts_cache_key, audio_path, srt_path = build_generated_tts_cache_paths(
                pid=pid,
                project_script=str(project.script or ""),
                voice_name=str(prep_ctx.voice_name or ""),
                voice_rate=str(prep_ctx.voice_rate or ""),
                channel_key=str(project.channel_key or ""),
                workflow=str(prep_ctx.wf or "mix"),
                stable_digest=stable_digest_bridge,
                project_audio_dir=project_audio_dir,
                project_subtitles_dir=project_subtitles_dir,
            )
            return (audio_path, srt_path)
    except Exception:
        return (None, None)


def llm_preflight(session, *, get_default_provider, get_api_key) -> tuple[bool, dict]:
    provider = get_default_provider(session)
    if not provider or not provider.enabled:
        return (False, {"message": "未配置默认大模型服务（设置 -> 大模型）", "error_code": "llm_config_missing", "blocking_component": "llm", "recommended_action": "go_settings_llm", "recoverable": True})
    api_key = ""
    if provider.id is not None:
        try:
            api_key = get_api_key(session, int(provider.id))
        except Exception:
            api_key = ""
    if str(provider.type or "") == "openai_compat" and not api_key:
        return (False, {"message": "未设置大模型接口密钥（设置 -> 大模型）", "error_code": "llm_config_missing", "blocking_component": "llm", "recommended_action": "go_settings_llm", "recoverable": True})
    if not str(provider.base_url or "").strip():
        return (False, {"message": "大模型服务地址未配置（设置 -> 大模型）", "error_code": "llm_config_missing", "blocking_component": "llm", "recommended_action": "go_settings_llm", "recoverable": True})
    if not str(provider.default_model or "").strip():
        return (False, {"message": "大模型名称未配置（设置 -> 大模型）", "error_code": "llm_config_missing", "blocking_component": "llm", "recommended_action": "go_settings_llm", "recoverable": True})
    return (True, {"provider": provider, "api_key": api_key})


def autopilot_preflight(session, project: Project, *, resume_stage: str | None, get_default_provider, get_api_key, tts_status_dict) -> tuple[bool, dict]:
    stage = normalize_autopilot_stage(resume_stage) or "storyboard"
    material_mode = project_material_mode(project)
    input_mode = project_input_mode(project)
    meta: dict = {"stage": stage, "material_mode": material_mode, "input_mode": input_mode}
    pid = int(getattr(project, "id", 0) or 0)
    if stage == "storyboard" and input_mode != "audio":
        ok, llm_meta = llm_preflight(session, get_default_provider=get_default_provider, get_api_key=get_api_key)
        if not ok:
            return (False, llm_meta)
        meta.update(llm_meta)
    if input_mode == "audio" and not getattr(project, "voice_asset_id", None):
        return (False, {"message": "当前项目为音频驱动模式，但还没有上传主音频。", "error_code": "audio_input_missing", "blocking_component": "project", "recommended_action": "open_project", "recoverable": True})
    if stage == "media":
        return resolve_visual_pipeline(material_mode).media_preflight(session=session, project=project)
    if stage in ("tts", "render") and input_mode != "audio" and not getattr(project, "voice_asset_id", None):
        if stage == "render" and pid > 0 and has_reusable_primary_audio_timeline(pid):
            meta["reuse_generated_tts"] = True
            meta["reuse_primary_audio_timeline"] = True
            return (True, meta)
        st = tts_status_dict(session=session, probe_edge=True)
        backend = str(st.get("backend") or "auto").strip().lower()
        edge_ok = bool(st.get("edge_synthesis_ok"))
        offline_ok = bool(st.get("offline_ok"))
        if backend == "edge" and not edge_ok:
            return (False, {"message": f"在线配音当前不可用：{humanize_autopilot_detail(str(st.get('edge_detail') or '请检查网络和在线配音设置'))}", "error_code": "tts_unavailable", "blocking_component": "tts", "recommended_action": "go_settings_tts", "recoverable": True})
        if backend == "offline_piper" and not offline_ok:
            return (False, {"message": f"离线配音当前不可用：{humanize_autopilot_detail(str(st.get('offline_detail') or '请先安装离线中文配音'))}", "error_code": "tts_unavailable", "blocking_component": "tts", "recommended_action": "go_settings_tts", "recoverable": True})
        if backend == "auto" and (not edge_ok) and (not offline_ok):
            return (False, {"message": "当前在线配音和离线配音都不可用，请先到 设置->配音 修复后再生成", "error_code": "tts_unavailable", "blocking_component": "tts", "recommended_action": "go_settings_tts", "recoverable": True})
        if backend == "edge":
            ok_audio, audio_msg = _edge_audio_pipeline_preflight()
        elif backend == "offline_piper":
            ok_audio, audio_msg = _audio_pipeline_preflight()
        else:
            ok_audio, audio_msg = _edge_audio_pipeline_preflight() if edge_ok else _audio_pipeline_preflight()
        if not ok_audio:
            return (False, {"message": audio_msg, "error_code": "tts_audio_env_unavailable", "blocking_component": "tts", "recommended_action": "go_settings_tts", "recoverable": True})
    return (True, meta)


def _rel_to_dir(p: Path, base: Path) -> str:
    return str(p.resolve().relative_to(base)).replace("\\", "/")


def autopilot_payload(job_id: int) -> dict:
    obj = get_job_payload(job_id)
    return obj if isinstance(obj, dict) else {}


def autopilot_stage_done(job_id: int, stage: str) -> bool:
    return bool(autopilot_payload(job_id).get(f"{stage}_done"))


def autopilot_resume_stage(job_id: int) -> str | None:
    raw = str(autopilot_payload(job_id).get("resume_from_stage") or "").strip().lower()
    return normalize_autopilot_stage(raw)


def autopilot_mark_stage(
    job_id: int,
    stage: str,
    *,
    status: str,
    detail: str | None = None,
    progress: int | None = None,
    message: str | None = None,
    substage: str | None = None,
) -> None:
    patch: dict[str, object | None] = {"current_stage": stage, "last_stage_status": status}
    if substage is not None:
        patch["current_substage"] = str(substage or "").strip().lower() or None
    if status == "done":
        patch[f"{stage}_done"] = True
        patch["last_failed_stage"] = None
        patch["resume_from_stage"] = None
        patch["last_error"] = None
        if stage != "render":
            patch["current_substage"] = None
    elif status == "failed":
        patch["last_failed_stage"] = stage
        patch["resume_from_stage"] = stage
        patch["last_error"] = str(detail or message or "")[:500]
    patch_job_payload(job_id, patch)
    if progress is not None or message is not None:
        update_job(job_id, progress=progress, message=message)


def autopilot_get_job_status(job_id: int) -> str:
    try:
        with session_scope() as session:
            j = session.exec(select(Job).where(Job.id == int(job_id))).first()
            return str(getattr(j, "status", "") or "") if j else ""
    except Exception:
        return ""


def autopilot_job_message(job_id: int) -> str:
    try:
        with session_scope() as session:
            j = session.exec(select(Job).where(Job.id == int(job_id))).first()
            return str(getattr(j, "message", "") or "") if j else ""
    except Exception:
        return ""


def autopilot_scene_stats(pid: int) -> tuple[int, int, int]:
    missing = 0
    total = 0
    try:
        with session_scope() as session:
            ss = list(session.exec(select(Scene).where(Scene.project_id == int(pid)).order_by(Scene.idx)).all())
            total = len(ss)
            for sc in ss:
                if not getattr(sc, "image_asset_id", None):
                    missing += 1
    except Exception:
        pass
    return missing, 0, total


def save_autopilot_storyboard(pid: int, script: str, scenes: list[dict], *, update_project_status: bool) -> bool:
    return save_storyboard(pid, script, scenes, update_project_status=update_project_status)


def run_autopilot_storyboard_stage(
    *,
    job_id: int,
    pid: int,
    title: str,
    src: str,
    project: Project,
    channel_key: str,
    character_profile: str,
    wf: str,
    pack: ChannelPack,
    provider: LlmProvider | None,
    api_key: str,
    render_cfg: dict | None,
    llm_rewrite_storyboard,
    llm_generate_storyboard,
) -> None:
    script = ""
    scenes: list[dict] = []
    autopilot_mark_stage(job_id, "storyboard", status="running", progress=8, message="生成视频：生成脚本/分镜", substage="generate_storyboard")
    wait_if_job_paused(job_id)
    try:
        material_mode = project_material_mode(project)
        if project_input_mode(project) == "audio":
            with session_scope() as session:
                audio_asset = session.exec(select(Asset).where(Asset.id == int(project.voice_asset_id or 0))).first() if getattr(project, "voice_asset_id", None) else None
            if not audio_asset:
                raise RuntimeError("音频驱动模式缺少主音频，请先上传音频后再生成。")
            script, scenes = build_audio_storyboard(pid, audio_asset=audio_asset, title=title)
        elif project_has_confirmed_baseline(project) and str(getattr(project, "script", "") or "").strip():
            script, scenes = build_confirmed_script_storyboard(str(getattr(project, "script", "") or "").strip(), pack=pack, render_cfg=render_cfg, material_mode=material_mode)
        elif src:
            script, scenes = llm_rewrite_storyboard(src, pack, provider, api_key, character_profile=character_profile, level="medium", workflow=wf, render_cfg=render_cfg, material_mode=material_mode)
        else:
            script, scenes = llm_generate_storyboard(title, pack, provider, api_key, character_profile=character_profile, workflow=wf, render_cfg=render_cfg, material_mode=material_mode)
    except Exception as e:
        code, detail = classify_llm_failure(e)
        raise RuntimeError(f"分镜大模型生成失败：{detail}") from LlmError(code)
    if not script or not scenes:
        raise RuntimeError("分镜大模型生成失败：返回结果为空")
    patch_job_payload(job_id, {"current_substage": "save_storyboard"})
    update_job(job_id, progress=22, message="生成视频：保存分镜")
    if not save_autopilot_storyboard(pid, script, scenes, update_project_status=True):
        autopilot_mark_stage(job_id, "storyboard", status="failed", detail="项目不存在", progress=100, message="项目不存在")
        update_job(job_id, status="failed", progress=100, message="项目不存在")
        raise RuntimeError("project_missing")
    if project_input_mode(project) != "audio" and not project_has_confirmed_baseline(project):
        patch_job_payload(job_id, {"current_substage": "compliance"})
        update_job(job_id, progress=28, message="生成视频：合规规则扫描")
        try:
            warns = check_text(script, channel_key=channel_key)
            has_block = any(w.get("level") == "block" for w in (warns or []))
        except Exception:
            has_block = False
        if has_block and provider and provider.enabled:
            patch_job_payload(job_id, {"current_substage": "compliance"})
            update_job(job_id, progress=32, message="生成视频：合规改写（保守）")
            try:
                script2, scenes2 = llm_rewrite_storyboard(script, pack, provider, api_key, character_profile=character_profile, level="safe", workflow=wf, render_cfg=render_cfg, material_mode=material_mode)
                if script2 and scenes2 and save_autopilot_storyboard(pid, script2, scenes2, update_project_status=False):
                    script = script2
            except Exception:
                pass
    autopilot_mark_stage(job_id, "storyboard", status="done")


def run_autopilot_media_stage(*, job_id: int, project_id: int, pid: int, wf: str, autofill_media_local, generate_images_local) -> None:
    from app.modules.visual.service import run_visual_stage

    with session_scope() as session:
        project = session.exec(select(Project).where(Project.id == int(project_id))).first()
    run_visual_stage(
        job_id=job_id,
        project_id=project_id,
        pid=pid,
        wf=wf,
        project=project,
        autofill_media_local=autofill_media_local,
        generate_images_local=generate_images_local,
        autopilot_mark_stage=autopilot_mark_stage,
        autopilot_get_job_status=autopilot_get_job_status,
        autopilot_job_message=autopilot_job_message,
        autopilot_payload=autopilot_payload,
        autopilot_scene_stats=autopilot_scene_stats,
        humanize_autopilot_detail=humanize_autopilot_detail,
        update_job=update_job,
        wait_if_job_paused=wait_if_job_paused,
    )


def run_autopilot_tts_stage(*, job_id: int, project_id: int, pid: int, resume_from_stage: str | None, prepare_project_tts_impl) -> None:
    reuse_generated_tts = False
    if resume_from_stage == "render":
        reuse_generated_tts = has_reusable_primary_audio_timeline(pid)
        if not reuse_generated_tts:
            logger.warning("tts files missing before render resume, will fall back to tts project_id={}", pid)
    if reuse_generated_tts:
        autopilot_mark_stage(job_id, "tts", status="done", progress=66, message="生成视频：复用已生成配音/字幕")
        return
    autopilot_mark_stage(job_id, "tts", status="running", progress=66, message="生成视频：生成配音/字幕", substage="generate_voice")
    prepare_project_tts_impl(job_id, project_id, progress_base=66, progress_span=8)
    if autopilot_get_job_status(job_id) in ("failed", "cancelled"):
        payload = autopilot_payload(job_id)
        detail = str(payload.get("last_error") or "").strip() or autopilot_job_message(job_id).strip() or "配音/字幕生成失败，请检查配音设置后重试。"
        autopilot_mark_stage(job_id, "tts", status="failed", detail=detail)
        raise RuntimeError(f"语音合成失败：{detail}")
    if not has_reusable_primary_audio_timeline(pid):
        detail = "配音/字幕生成失败：未找到可复用的配音或字幕文件。"
        autopilot_mark_stage(job_id, "tts", status="failed", detail=detail)
        raise RuntimeError(detail)
    autopilot_mark_stage(job_id, "tts", status="done", progress=74, message="生成视频：配音/字幕已完成")


def run_autopilot_render_stage(*, job_id: int, project_id: int, pid: int, candidate_batch_id: str, resume_from_stage: str | None, render_video_impl, fail_job) -> None:
    render_substage = str(autopilot_payload(job_id).get("render_substage") or "").strip().lower()
    if render_substage in ("silent_track_ready", "mux_prepare", "finalize_output"):
        update_job(job_id, progress=74, message="生成视频：复用已生成配音/字幕与静音视频轨，继续最终合成")
    else:
        update_job(job_id, progress=74, message="生成视频：生成最终成片")
    autopilot_mark_stage(job_id, "render", status="running")
    wait_if_job_paused(job_id)
    render_video_impl(job_id, project_id, outer_job_id=job_id, progress_base=74, progress_span=18, keep_running=True, reuse_generated_tts=True, require_existing_tts=True)
    if autopilot_get_job_status(job_id) in ("failed", "cancelled"):
        payload = autopilot_payload(job_id)
        detail = str(payload.get("last_error") or "").strip()
        if not detail and autopilot_get_job_status(job_id) == "failed":
            detail = autopilot_job_message(job_id).strip()
        if not detail:
            detail = "最终成片生成失败，请从渲染阶段继续。"
        render_substage_now = str(payload.get("render_substage") or render_substage or "").strip().lower()
        if render_substage_now in ("silent_track_prepare", "silent_track_ready", "mux_prepare", "finalize_output", "done") or bool(payload.get("tts_done")):
            autopilot_mark_stage(job_id, "render", status="failed", detail=detail)
            raise RuntimeError(f"视频渲染失败：{detail}")
        autopilot_mark_stage(job_id, "render", status="failed", detail=detail)
        raise RuntimeError(f"渲染过程失败：{detail}")
    final_path = (project_exports_dir(int(pid)) / "final.mp4").resolve()
    try:
        final_ok = final_path.exists() and final_path.is_file() and final_path.stat().st_size > 0
    except Exception:
        autopilot_mark_stage(job_id, "render", status="failed", detail="final_check_failed")
        fail_job(job_id, message="最终成片渲染失败：无法校验最终成片文件，请从渲染阶段继续。", error_code="render_failed", blocking_component="render", recommended_action="continue_from_project", recoverable=True)
        raise
    if not final_ok:
        autopilot_mark_stage(job_id, "render", status="failed", detail="final_missing")
        fail_job(job_id, message="最终成片渲染失败：未找到最终成片文件，请从渲染阶段继续。", error_code="final_missing", blocking_component="render", recommended_action="continue_from_project", recoverable=True)
        raise RuntimeError("最终成片生成失败，请从渲染阶段继续。")
    miss, _rev, total = autopilot_scene_stats(pid)
    autopilot_mark_stage(job_id, "render", status="done")
    update_job(job_id, status="done", progress=100, message=f"生成视频完成（最终成片已生成）· 镜头缺失 {miss}/{max(1, total)}")


def get_pack(session, channel_key: str) -> ChannelPack | None:
    return session.exec(select(ChannelPack).where(ChannelPack.key == channel_key)).first()


def autopilot_run_impl(
    job_id: int,
    project_id: int,
    *,
    fail_job,
    llm_generate_storyboard,
    llm_rewrite_storyboard,
    render_video_impl,
    autofill_media_local,
    generate_images_local,
    get_default_provider,
    get_api_key,
) -> None:
    run_pipeline_job(
        job_id,
        project_id,
        fail_job=fail_job,
        llm_generate_storyboard=llm_generate_storyboard,
        llm_rewrite_storyboard=llm_rewrite_storyboard,
        render_video_impl=render_video_impl,
        autofill_media_local=autofill_media_local,
        generate_images_local=generate_images_local,
        get_default_provider=get_default_provider,
        get_api_key=get_api_key,
    )
