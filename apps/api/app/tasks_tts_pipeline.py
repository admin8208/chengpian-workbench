import json
import re
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import select

from app.db import session_scope
from app.ffmpeg_utils import ffmpeg_path, run_ffmpeg
from app.jobs import is_job_cancelled, patch_job_payload, wait_if_job_paused
from app.models import Scene
from app.project_paths import project_subtitles_dir
from app.settings import settings
from app.storyboard_postprocess import humanize_scene_durations
from app.subtitles import clean_tts_text, naive_srt_from_lines, naive_srt_from_scenes


@dataclass
class AudioSubtitlePrepResult:
    audio_path: Path
    srt_path: Path
    audio_duration: float
    base_durs: list[float]
    tts_failed: bool
    tts_error: str
    tts_backend_used: str


def subtitle_stats(p: Path) -> tuple[int, float]:
    try:
        if (not p.exists()) or p.stat().st_size <= 0:
            return (0, 0.0)
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if not txt.strip():
            return (0, 0.0)
        cue_count = 0
        last_end = 0.0
        lines = [ln.strip() for ln in txt.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
        for ln in lines:
            if "-->" not in ln:
                continue
            cue_count += 1
            try:
                rhs = ln.split("-->", 1)[1].strip()
                hms, ms = rhs.split(",", 1)
                hh, mm, ss = [int(x) for x in hms.split(":")]
                end_s = float(hh * 3600 + mm * 60 + ss) + float(int(ms[:3])) / 1000.0
                if end_s > last_end:
                    last_end = end_s
            except Exception:
                pass
        return (cue_count, last_end)
    except Exception:
        return (0, 0.0)


def subtitle_alignment_ok(p: Path, *, audio_sec: float) -> tuple[bool, str]:
    try:
        if (not p.exists()) or p.stat().st_size <= 0:
            return (False, "subtitle_missing")
        txt = p.read_text(encoding="utf-8", errors="ignore")
        lines = [ln.strip() for ln in txt.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
        starts: list[float] = []
        ends: list[float] = []
        for ln in lines:
            if "-->" not in ln:
                continue
            try:
                lhs, rhs = [x.strip() for x in ln.split("-->", 1)]

                def _to_sec(x: str) -> float:
                    hms, ms = x.split(",", 1)
                    hh, mm, ss = [int(v) for v in hms.split(":")]
                    return float(hh * 3600 + mm * 60 + ss) + float(int(ms[:3])) / 1000.0

                starts.append(_to_sec(lhs))
                ends.append(_to_sec(rhs.split()[0]))
            except Exception:
                continue
        if not starts or not ends:
            return (False, "subtitle_empty")
        min_seg = min(max(0.0, e - s) for s, e in zip(starts, ends))
        max_gap = max([0.0] + [max(0.0, starts[i] - ends[i - 1]) for i in range(1, min(len(starts), len(ends)))])
        if min_seg < 0.30:
            return (False, "subtitle_segment_too_short")
        if audio_sec > 0 and max_gap > max(0.45, audio_sec * 0.08):
            return (False, "subtitle_gap_too_large")
        final_delta = abs(float(audio_sec) - float(max(ends))) if audio_sec > 0 else 0.0
        if audio_sec > 0 and final_delta > max(0.65, audio_sec * 0.08):
            return (False, "subtitle_end_mismatch")
        return (True, "ok")
    except Exception:
        return (False, "subtitle_check_error")


def subtitle_text_coverage_ok(p: Path, *, expected_text: str) -> tuple[bool, float]:
    def _norm(s: str) -> str:
        return "".join(re.findall(r"[0-9A-Za-z\u4e00-\u9fff]", str(s or "")))

    try:
        exp = _norm(expected_text)
        if not exp:
            return (True, 1.0)
        if (not p.exists()) or p.stat().st_size <= 0:
            return (False, 0.0)
        txt = p.read_text(encoding="utf-8", errors="ignore")
        got = _norm(txt)
        if not got:
            return (False, 0.0)
        ratio = min(1.0, float(len(got)) / float(max(1, len(exp))))
        return (ratio >= 0.82, ratio)
    except Exception:
        return (False, 0.0)


def _format_srt_time(sec: float) -> str:
    total_ms = max(0, int(round(float(sec or 0.0) * 1000.0)))
    hh = total_ms // 3600000
    mm = (total_ms % 3600000) // 60000
    ss = (total_ms % 60000) // 1000
    ms = total_ms % 1000
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def build_scene_srt_from_audio_segments(*, scenes, audio_duration: float) -> str:
    cues: list[tuple[float, float, str]] = []
    for scene in scenes:
        text = clean_tts_text(getattr(scene, "narration", "") or "")
        if not text:
            continue
        meta = {}
        try:
            meta = json.loads(getattr(scene, "meta_json", "{}") or "{}")
        except Exception:
            meta = {}
        try:
            start_sec = float(meta.get("audio_start_sec") or 0.0)
            end_sec = float(meta.get("audio_end_sec") or 0.0)
        except Exception:
            start_sec = 0.0
            end_sec = 0.0
        if end_sec <= start_sec:
            continue
        cues.append((start_sec, end_sec, text))
    if not cues:
        return ""
    cues.sort(key=lambda item: item[0])
    total_audio = max(0.0, float(audio_duration or 0.0))
    rows: list[str] = []
    for idx, (start_sec, end_sec, text) in enumerate(cues, start=1):
        safe_start = max(0.0, start_sec)
        safe_end = max(safe_start + 0.2, end_sec)
        if total_audio > 0:
          safe_end = min(total_audio, safe_end)
        rows.append(str(idx))
        rows.append(f"{_format_srt_time(safe_start)} --> {_format_srt_time(safe_end)}")
        rows.append(text)
        rows.append("")
    return "\n".join(rows).strip() + "\n"


def build_scene_srt_fallback(*, pid: int, name: str, scenes=None, scene_texts: list[str], base_durs: list[float], script_text: str, audio_duration: float) -> Path | None:
    try:
        timed_srt = build_scene_srt_from_audio_segments(scenes=scenes or [], audio_duration=audio_duration)
        if timed_srt:
            tmp = project_subtitles_dir(pid) / name
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(timed_srt, encoding="utf-8")
            return tmp
        safe_scene_texts = [clean_tts_text(x) for x in scene_texts]
        safe_script_text = clean_tts_text(script_text)
        srt_fallback = naive_srt_from_scenes(safe_scene_texts, base_durs)
        if not srt_fallback:
            srt_fallback = naive_srt_from_lines(safe_script_text, total_duration=audio_duration)
        if not srt_fallback:
            return None
        tmp = project_subtitles_dir(pid) / name
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(srt_fallback, encoding="utf-8")
        return tmp
    except Exception:
        return None


def ensure_silent_voice_mp3(audio_path: Path, *, duration_sec: float) -> None:
    try:
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        dur = max(1.0, float(duration_sec or 1.0))
        run_ffmpeg([
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t",
            f"{dur:.3f}",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "128k",
            ffmpeg_path(audio_path),
        ], timeout_s=45)
    except Exception:
        pass


def prepare_audio_and_subtitles(
    *,
    job_id: int,
    target_job_id: int,
    pid: int,
    project,
    scenes,
    script_text: str,
    audio_path: Path,
    srt_path: Path,
    has_voice_upload: bool,
    has_subtitle_upload: bool,
    require_tts: bool,
    planned_duration: float,
    base_durs: list[float],
    voice_name: str,
    voice_rate: str,
    reuse_generated_tts: bool,
    temp_file_prefix: str,
    on_update,
    friendly_tts_failure_message,
    subtitle_has_visible_cues,
    stage_switch_to_render: bool = True,
) -> AudioSubtitlePrepResult:
    from moviepy import AudioFileClip

    if target_job_id:
        patch_job_payload(target_job_id, {"render_substage": "tts_prepare"})
    on_update(progress=52, message="生成配音/字幕")
    wait_if_job_paused(target_job_id)
    if is_job_cancelled(job_id):
        raise RuntimeError("cancelled")

    tts_backend_used = ""
    scene_caption_texts: list[str] | None = None
    generated_audio_exists = audio_path.exists() and audio_path.is_file() and audio_path.stat().st_size > 0
    generated_srt_exists = srt_path.exists() and srt_path.is_file() and srt_path.stat().st_size > 0

    if reuse_generated_tts and not has_voice_upload and not has_subtitle_upload and generated_audio_exists and generated_srt_exists:
        tts_backend_used = "reuse"
        if target_job_id:
            patch_job_payload(target_job_id, {"render_substage": "tts_ready"})
        on_update(progress=58, message="复用已生成配音/字幕")
    elif not has_voice_upload and has_subtitle_upload:
        if target_job_id:
            patch_job_payload(target_job_id, {"render_substage": "tts_prepare"})
        on_update(progress=56, message="检测到仅上传字幕，已补静音音轨用于渲染")
        ensure_silent_voice_mp3(audio_path, duration_sec=planned_duration)
        if (not audio_path.exists()) or audio_path.stat().st_size <= 0:
            raise RuntimeError("仅上传字幕时，无法生成静音音轨。请重试，或同时上传配音文件。")
        tts_backend_used = "上传字幕（静音音轨）"
    elif not has_voice_upload and not has_subtitle_upload:
        try:
            from app.modules.tts.offline import offline_tts_status
            from app.modules.tts.runtime import edge_tts_to_files
            from app.modules.tts.service import edge_synthesis_probe_cached, get_offline_voice_id, get_tts_backend
            from app.modules.tts.smart import is_drama_like, smart_tts_generate

            with session_scope() as session:
                pref = get_tts_backend(session)
                off_vid = get_offline_voice_id(session)
            backend = "offline_piper"
            if pref == "edge":
                backend = "edge"
            elif pref == "auto":
                ok, _detail, _checked = edge_synthesis_probe_cached(voice=voice_name, rate=voice_rate, timeout_s=20, ttl_s=180, force=False)
                backend = "edge" if ok else "offline_piper"

            if backend == "offline_piper":
                st = offline_tts_status(voice_id=off_vid, probe=False)
                if not st.installed:
                    raise RuntimeError("离线配音未安装：请到 设置->配音 一键安装离线中文配音")

            sc_list: list[tuple[int, str]] = []
            sc_meta: list[str] = []
            with session_scope() as session:
                ss = session.exec(select(Scene).where(Scene.project_id == int(pid)).order_by(Scene.idx)).all()
                for s in ss:
                    sc_list.append((int(s.idx), str(s.narration or "").strip()))
                    sc_meta.append(str(getattr(s, "meta_json", "{}") or "{}"))
            track_key = str(getattr(project, "channel_key", "") or "")
            is_drama_like(title=str(project.title or ""), scenes=sc_list, scene_meta_json=sc_meta)

            def _run_smart(*, backend2: str) -> tuple[str, list[str] | None]:
                used, caps = smart_tts_generate(
                    project_id=int(pid),
                    project_title=str(project.title or ""),
                    scenes=sc_list,
                    scene_meta_json=sc_meta,
                    backend=backend2,
                    offline_voice_id=str(off_vid),
                    edge_voice_default=str(voice_name),
                    edge_rate_default=str(voice_rate),
                    audio_path=audio_path,
                    srt_path=srt_path,
                    track_key=track_key,
                )
                if isinstance(caps, list) and len(caps) == len(scenes):
                    return used, caps
                idx_to_cap = {int(idx): str(nar or "").strip() for idx, nar in sc_list}
                return used, [idx_to_cap.get(int(getattr(s, "idx", 0) or 0), str(getattr(s, "narration", "") or "").strip()) for s in scenes]

            def _run_edge_narrator() -> tuple[str, list[str] | None]:
                audio_path.parent.mkdir(parents=True, exist_ok=True)
                srt_path.parent.mkdir(parents=True, exist_ok=True)
                edge_tts_to_files(text=script_text, voice=str(voice_name), rate=str(voice_rate), audio_path=audio_path, srt_path=srt_path, words_in_cue=8, timeout_s=240)
                idx_to_cap = {int(idx): str(nar or "").strip() for idx, nar in sc_list}
                return "edge", [idx_to_cap.get(int(getattr(s, "idx", 0) or 0), str(getattr(s, "narration", "") or "").strip()) for s in scenes]

            try:
                tts_backend_used, scene_caption_texts = _run_smart(backend2=backend)
            except Exception:
                if backend == "edge" and pref == "auto":
                    st3 = offline_tts_status(voice_id=off_vid, probe=False)
                    if st3.installed:
                        tts_backend_used, scene_caption_texts = _run_smart(backend2="offline_piper")
                    else:
                        tts_backend_used, scene_caption_texts = _run_edge_narrator()
                else:
                    raise
        except Exception as e:
            raise RuntimeError(friendly_tts_failure_message(str(e))[:900]) from e

    try:
        audio_clip = AudioFileClip(str(audio_path))
        audio_duration = float(audio_clip.duration)
        audio_clip.close()
    except Exception:
        audio_duration = 0.0
    if audio_duration <= 0:
        audio_duration = planned_duration

    if audio_duration > 0:
        try:
            def _w(t: str) -> float:
                s = (t or "").strip()
                if not s:
                    return 1.0
                n = len(re.findall(r"[0-9A-Za-z\u4e00-\u9fff]", s))
                return float(max(1, min(120, n)))

            weights = [_w(getattr(s, "narration", "") or "") for s in scenes]
            sw = float(sum(weights)) if weights else 0.0
            if sw <= 0:
                weights = [1.0 for _ in scenes]
                sw = float(len(scenes))
            alloc = [max(2.0, float(audio_duration) * (w / sw)) for w in weights]
            sa = float(sum(alloc))
            if sa > 0:
                scale = float(audio_duration) / sa
                alloc = [max(2.0, d * scale) for d in alloc]
            base_durs = humanize_scene_durations(alloc, total_duration=float(audio_duration))
        except Exception:
            pass

    cue_count, subtitle_end_sec = subtitle_stats(srt_path)
    coverage_ratio = (float(subtitle_end_sec) / float(audio_duration)) if audio_duration > 0 else 1.0
    need_sub_fallback = audio_duration > 0 and ((not subtitle_has_visible_cues(srt_path)) or cue_count < 2 or coverage_ratio < 0.9)
    scene_texts = [str(x or "").strip() for x in scene_caption_texts] if isinstance(scene_caption_texts, list) and len(scene_caption_texts) == len(scenes) else [(getattr(s, "narration", "") or "").strip() for s in scenes]
    expected_subtitle_text = "\n".join([x for x in scene_texts if x]) or script_text

    text_ok, text_ratio = subtitle_text_coverage_ok(srt_path, expected_text=expected_subtitle_text)
    if not text_ok:
        need_sub_fallback = True

    if need_sub_fallback:
        tmp = build_scene_srt_fallback(pid=pid, name=f"{temp_file_prefix}_subtitle_naive.srt", scenes=scenes, scene_texts=scene_texts, base_durs=base_durs, script_text=script_text, audio_duration=audio_duration)
        if tmp:
            srt_path = tmp
            if target_job_id:
                patch_job_payload(target_job_id, {"render_substage": "tts_prepare"})
            on_update(progress=58, message="字幕源异常，已按音频时长自动重建字幕")
            text_ok, text_ratio = subtitle_text_coverage_ok(srt_path, expected_text=expected_subtitle_text)

    aligned_ok, aligned_reason = subtitle_alignment_ok(srt_path, audio_sec=float(audio_duration))
    if require_tts and not aligned_ok:
        tmp = build_scene_srt_fallback(pid=pid, name=f"{temp_file_prefix}_subtitle_naive.srt", scenes=scenes, scene_texts=[(getattr(s, "narration", "") or "").strip() for s in scenes], base_durs=base_durs, script_text=script_text, audio_duration=audio_duration)
        if tmp:
            srt_path = tmp
            aligned_ok, aligned_reason = subtitle_alignment_ok(srt_path, audio_sec=float(audio_duration))
            if aligned_ok:
                if target_job_id:
                    patch_job_payload(target_job_id, {"render_substage": "tts_prepare"})
                on_update(progress=59, message="字幕切换时机已自动修正")
            text_ok, text_ratio = subtitle_text_coverage_ok(srt_path, expected_text=expected_subtitle_text)

    if require_tts and not aligned_ok:
        tmp = build_scene_srt_fallback(pid=pid, name=f"{temp_file_prefix}_subtitle_repair.srt", scenes=scenes, scene_texts=scene_texts, base_durs=base_durs, script_text=script_text, audio_duration=audio_duration)
        if tmp:
            srt_path = tmp
            aligned_ok, aligned_reason = subtitle_alignment_ok(srt_path, audio_sec=float(audio_duration))
            if aligned_ok:
                if target_job_id:
                    patch_job_payload(target_job_id, {"render_substage": "tts_prepare"})
                on_update(progress=59, message="字幕时间轴已二次修复")
            text_ok, text_ratio = subtitle_text_coverage_ok(srt_path, expected_text=expected_subtitle_text)

    if require_tts:
        try:
            if (not srt_path.exists()) or srt_path.stat().st_size == 0:
                raise RuntimeError("字幕生成失败：未生成有效字幕文件。可尝试重新渲染，或在项目中手动上传字幕文件。")
            quality_warnings: list[str] = []
            cue_count2, subtitle_end_sec2 = subtitle_stats(srt_path)
            visible_ok2 = subtitle_has_visible_cues(srt_path)
            coverage_ratio2 = (float(subtitle_end_sec2) / float(audio_duration)) if audio_duration > 0 else 1.0
            if (not visible_ok2) or cue_count2 < 2:
                tmp = build_scene_srt_fallback(pid=pid, name=f"{temp_file_prefix}_subtitle_last_rescue.srt", scenes=scenes, scene_texts=[(getattr(s, "narration", "") or "").strip() for s in scenes], base_durs=base_durs, script_text=script_text, audio_duration=audio_duration)
                if tmp and tmp.exists() and tmp.stat().st_size > 0:
                    srt_path = tmp
                    cue_count2, subtitle_end_sec2 = subtitle_stats(srt_path)
                    visible_ok2 = subtitle_has_visible_cues(srt_path)
                    coverage_ratio2 = (float(subtitle_end_sec2) / float(audio_duration)) if audio_duration > 0 else 1.0
                    text_ok, text_ratio = subtitle_text_coverage_ok(srt_path, expected_text=expected_subtitle_text)
                    aligned_ok, aligned_reason = subtitle_alignment_ok(srt_path, audio_sec=float(audio_duration))
            if (not visible_ok2) or cue_count2 < 2:
                raise RuntimeError("字幕生成失败：字幕为空或条数过少，请重试或手动上传字幕。")
            if not text_ok:
                quality_warnings.append(f"字幕内容覆盖不足（{int(text_ratio * 100)}%）")
            if not aligned_ok:
                quality_warnings.append(f"字幕与音频未完全对齐（{aligned_reason}）")
            if coverage_ratio2 < 0.90:
                quality_warnings.append(f"字幕覆盖时长不足（{int(coverage_ratio2 * 100)}%）")
            if quality_warnings:
                if target_job_id:
                    patch_job_payload(target_job_id, {"render_substage": "tts_prepare"})
                on_update(progress=59, message=f"字幕已自动修复并继续渲染：{'；'.join(quality_warnings[:2])}")
                try:
                    patch_job_payload(target_job_id, {"subtitle_warnings": quality_warnings[:6]})
                except Exception:
                    pass
        except Exception as e:
            raise RuntimeError(str(e) or "字幕生成失败：无法校验字幕文件。") from e

    if target_job_id:
        patch: dict[str, object | None] = {"tts_done": True}
        if stage_switch_to_render:
            patch["render_substage"] = "tts_ready"
        patch_job_payload(target_job_id, patch)

    return AudioSubtitlePrepResult(
        audio_path=audio_path,
        srt_path=srt_path,
        audio_duration=float(audio_duration),
        base_durs=base_durs,
        tts_failed=False,
        tts_error="",
        tts_backend_used=tts_backend_used,
    )
