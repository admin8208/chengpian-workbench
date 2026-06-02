from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session, select

from app.access_control import require_project_access
from app.db import session_scope
from app.llm_client import LlmChatMessage, LlmError
from app.llm_service import get_api_key, get_default_provider
from app.models import Asset, ChannelPack, LlmProvider, Project
from app.modules.baseline.repository import create_baseline_revision
from app.tasks_autopilot import build_audio_storyboard, classify_llm_failure
from app.tasks_storyboard import llm_generate_storyboard
from app.storyboard_service import call_llm_json
from app.time_utils import now_utc


def _target_script_chars(render_cfg: dict) -> int:
    try:
        target_sec = float((render_cfg or {}).get("target_sec") or 60.0)
    except Exception:
        target_sec = 60.0
    return max(120, min(900, int(target_sec * 4.2)))


def _script_max_tokens(target_chars: int) -> int:
    return max(384, min(1600, int(target_chars * 1.8) + 256))


def _extract_script(obj: dict) -> str:
    if not isinstance(obj, dict):
        return ""
    candidates = [obj.get("script"), obj.get("draft"), obj.get("text"), obj.get("content")]
    for item in candidates:
        text = str(item or "").strip()
        if text:
            return text
    lines = obj.get("lines")
    if isinstance(lines, list):
        text = "\n".join(str(x).strip() for x in lines if str(x).strip()).strip()
        if text:
            return text
    return ""


def llm_generate_script_draft(
    *,
    title: str,
    source_text: str,
    pack: ChannelPack,
    provider: LlmProvider,
    api_key: str,
    character_profile: str = "",
    render_cfg: dict | None = None,
) -> str:
    target_chars = _target_script_chars(render_cfg or {})
    source = str(source_text or "").strip()
    topic = str(title or "当前主题").strip() or "当前主题"
    system = "\n".join(
        [
            "你是短视频口播文案导演，只负责生成可编辑的口播文案草稿，不生成分镜。",
            "只返回严格 JSON，不要 Markdown，不要代码块，不要解释。",
            'JSON 格式必须是：{"script":"..."}',
            "文案要自然、口语化、可直接配音；不要输出 scenes、镜头、图片提示词或素材检索词。",
        ]
    )
    user_parts = [
        f"频道：{getattr(pack, 'name', '') or getattr(pack, 'key', '')}",
        f"主题：{topic}",
        f"目标字数：约 {target_chars} 个中文字符",
        f"人物/角色设定：{character_profile}" if str(character_profile or "").strip() else "",
    ]
    if source:
        user_parts.extend(
            [
                "任务：根据原文/要点改写成一段完整口播文案，保留核心信息，表达更适合短视频。",
                f"原文/要点：\n{source[:6000]}",
            ]
        )
    else:
        user_parts.append("任务：围绕主题生成一段完整口播文案。")
    obj = call_llm_json(
        provider=provider,
        api_key=api_key,
        messages=[LlmChatMessage(role="system", content=system), LlmChatMessage(role="user", content="\n".join(x for x in user_parts if x))],
        timeout_s=120,
        max_tokens=_script_max_tokens(target_chars),
    )
    script = _extract_script(obj)
    if not script:
        raise LlmError("文案生成返回 JSON 中缺少 script 字段")
    return script


def load_project_pack_and_provider(session: Session, project_id: int) -> tuple[Project, ChannelPack, LlmProvider | None, str, dict]:
    project = require_project_access(session, project_id)
    pack = session.exec(select(ChannelPack).where(ChannelPack.key == project.channel_key)).first()
    if not pack:
        raise HTTPException(status_code=400, detail="未知的频道 key")
    provider = get_default_provider(session)
    api_key = get_api_key(session, int(provider.id)) if provider and provider.id is not None else ""
    render_cfg = project.render_config() if hasattr(project, "render_config") else {}
    if not isinstance(render_cfg, dict):
        render_cfg = {}
    return project, pack, provider, api_key, render_cfg


def generate_script_draft(*, project: Project, pack: ChannelPack, provider: LlmProvider | None, api_key: str, render_cfg: dict) -> tuple[str, str]:
    title = str(project.title or "").strip()
    source_text = str(project.source_text or "").strip()
    workflow = str(getattr(project, "workflow", "mix") or "mix").strip().lower() or "mix"
    character_profile = str(getattr(project, "character_profile", "") or "").strip()
    input_mode = str((render_cfg or {}).get("input_mode") or "text").strip().lower() or "text"

    if input_mode == "audio":
        if not getattr(project, "voice_asset_id", None):
            raise HTTPException(status_code=400, detail="音频驱动模式缺少主音频，请先上传音频后再生成")
        with session_scope() as inner_session:
            audio_asset = inner_session.exec(select(Asset).where(Asset.id == int(project.voice_asset_id or 0))).first()
        if not audio_asset:
            raise HTTPException(status_code=400, detail="音频驱动模式缺少主音频，请先上传音频后再生成")
        script, _scenes = build_audio_storyboard(int(project.id or 0), audio_asset=audio_asset, title=title)
        if not script:
            raise HTTPException(status_code=502, detail="生成文案失败：返回结果为空")
        return script, "audio_transcribe"

    try:
        if not provider or not provider.enabled:
            raise HTTPException(status_code=409, detail="未配置默认大模型服务（设置 -> 大模型）")
        script = llm_generate_script_draft(
            title=title,
            source_text=source_text,
            pack=pack,
            provider=provider,
            api_key=api_key,
            character_profile=character_profile,
            render_cfg=render_cfg,
        )
    except HTTPException:
        raise
    except Exception as exc:
        code, detail = classify_llm_failure(exc)
        if code == "llm_bad_response":
            detail = "大模型没有返回有效文案，请重试或调整输入"
        raise HTTPException(status_code=502, detail=f"生成文案失败：{detail}") from LlmError(code)

    if not script:
        raise HTTPException(status_code=502, detail="生成文案失败：返回结果为空")
    return script, "llm"


def generate_storyboard_draft(*, project: Project, pack: ChannelPack, provider: LlmProvider | None, api_key: str, render_cfg: dict) -> tuple[str, list[dict]]:
    title = str(getattr(project, "title", "") or "").strip()
    source_text = str(getattr(project, "source_text", "") or "").strip()
    workflow = str(getattr(project, "workflow", "mix") or "mix").strip().lower() or "mix"
    character_profile = str(getattr(project, "character_profile", "") or "").strip()
    input_mode = str((render_cfg or {}).get("input_mode") or "text").strip().lower() or "text"

    if input_mode == "audio" and not getattr(project, "voice_asset_id", None):
        raise HTTPException(status_code=400, detail="音频驱动模式缺少主音频，请先上传音频后再生成")

    try:
        if not provider or not getattr(provider, "enabled", False):
            raise HTTPException(status_code=409, detail="未配置默认大模型服务（设置 -> 大模型）")
        script, scenes = llm_generate_storyboard(
            title,
            pack,
            provider,
            api_key,
            character_profile=character_profile,
            workflow=workflow,
            render_cfg=render_cfg,
            material_mode=str((render_cfg or {}).get("material_mode") or ""),
        )
    except HTTPException:
        raise
    except Exception as exc:
        code, detail = classify_llm_failure(exc)
        if code == "llm_bad_response":
            detail = "大模型没有返回有效文案，请重试或调整输入"
        raise HTTPException(status_code=502, detail=f"生成文案失败：{detail}") from LlmError(code)

    if not script:
        raise HTTPException(status_code=502, detail="生成文案失败：返回结果为空")
    return script, scenes


def prepare_project_script(project_id: int, *, project_to_out) -> object:
    with session_scope() as session:
        project, pack, provider, api_key, render_cfg = load_project_pack_and_provider(session, project_id)
    script, script_source = generate_script_draft(project=project, pack=pack, provider=provider, api_key=api_key, render_cfg=render_cfg)
    with session_scope() as session:
        project = require_project_access(session, int(project_id))
        input_mode = str((project.render_config() or {}).get("input_mode") or "text").strip().lower() or "text"
        project.script = script
        project.script_source = script_source
        voice_asset_id = int(project.voice_asset_id or 0) if getattr(project, "voice_asset_id", None) else None
        create_baseline_revision(
            session,
            project=project,
            input_mode=input_mode,
            script_text=script,
            source=script_source,
            audio_asset_id=voice_asset_id,
            status="draft",
        )
        project.updated_at = now_utc()
        session.add(project)
        session.flush()
        session.refresh(project)
        return project_to_out(session, project)


def start_prepare_project_script_api(project_id: int):
    from app.job_dispatcher import enqueue_project_job
    from app.tasks_entries import prepare_project_script as prepare_project_script_job

    with session_scope() as session:
        require_project_access(session, int(project_id))
    return enqueue_project_job(
        kind="script_prepare",
        project_id=project_id,
        message="排队中",
        payload={"project_id": project_id, "current_stage": "baseline_prepare"},
        enqueue=lambda job_id: prepare_project_script_job.schedule(args=(job_id, project_id), delay=0),
        enqueue_error_message="文案生成任务入队失败，请检查后台任务服务",
    )


def confirm_project_script(project_id: int, *, script: str | None, project_to_out) -> object:
    with session_scope() as session:
        project = require_project_access(session, int(project_id))
        next_script = str(script if script is not None else getattr(project, "script", "") or "").strip()
        if not next_script:
            raise HTTPException(status_code=400, detail="请先生成或填写文案后再确认")
        input_mode = str((project.render_config() or {}).get("input_mode") or "text").strip().lower() or "text"
        voice_asset_id = int(project.voice_asset_id or 0) if getattr(project, "voice_asset_id", None) else None
        rev = create_baseline_revision(
            session,
            project=project,
            input_mode=input_mode,
            script_text=next_script,
            source=(str(getattr(project, "script_source", "") or "").strip() or "manual"),
            audio_asset_id=voice_asset_id,
            status="confirmed",
        )
        project.script = next_script
        if not str(getattr(project, "script_source", "") or "").strip():
            project.script_source = "manual"
        project.confirmed_baseline_revision_id = int(rev.id) if rev.id is not None else None
        project.updated_at = now_utc()
        session.add(project)
        session.flush()
        session.refresh(project)
        return project_to_out(session, project)
