from __future__ import annotations

from loguru import logger
from sqlmodel import select

from app.db import session_scope
from app.jobs import patch_job_payload, update_job, wait_if_job_paused
from app.logging_setup import sanitize_log_text
from app.models import ChannelPack, Project
from app.modules.visual.service import run_visual_stage
from app.modules.pipeline.repository import update_pipeline_run_stage
from app.modules.pipeline.state import normalize_autopilot_stage
from app.modules.tts.service import tts_status_dict
from app.time_utils import now_utc


def run_pipeline_job(
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
    from app.tasks_autopilot import (
        AUTOPILOT_STAGES,
        autopilot_get_job_status,
        autopilot_job_message,
        autopilot_mark_stage,
        autopilot_payload,
        autopilot_preflight,
        autopilot_resume_stage,
        autopilot_scene_stats,
        autopilot_stage_done,
        classify_llm_failure,
        get_pack,
        humanize_autopilot_detail,
        run_autopilot_render_stage,
        run_autopilot_storyboard_stage,
        run_autopilot_tts_stage,
    )
    from app.tasks_render_facade import prepare_project_tts_local

    update_job(job_id, status="running", progress=1, message="生成视频：准备中")
    wait_if_job_paused(job_id)
    try:
        pipeline_run_id = 0
        with session_scope() as session:
            project = session.exec(select(Project).where(Project.id == project_id)).first()
            if not project or project.id is None:
                update_job(job_id, status="failed", progress=100, message="项目不存在")
                return
            pid = int(project.id)
            pack = get_pack(session, project.channel_key)
            if not pack:
                fail_job(job_id, message="频道内容包不存在", error_code="channel_pack_missing", blocking_component="project", recommended_action="open_project", recoverable=False)
                return
            wf = "mix"
            title = (project.title or "").strip()
            src = (getattr(project, "source_text", "") or "").strip()
            character_profile = (project.character_profile or "").strip()
            channel_key = str(project.channel_key or "")
            render_cfg = project.render_config() if hasattr(project, "render_config") else {}
            old_payload = autopilot_payload(job_id)
            pipeline_run_id = int(old_payload.get("pipeline_run_id") or getattr(project, "current_pipeline_run_id", 0) or 0)
            candidate_batch_id = str(old_payload.get("candidate_batch_id") or "").strip() or f"ap_{job_id}_{now_utc().strftime('%Y%m%d_%H%M%S')}"
            resume_from_stage = normalize_autopilot_stage(autopilot_resume_stage(job_id))
            ok, meta = autopilot_preflight(session, project, resume_stage=resume_from_stage, get_default_provider=get_default_provider, get_api_key=get_api_key, tts_status_dict=tts_status_dict)
            if not ok:
                fail_job(job_id, message=str(meta.get("message") or "生成视频前置检查失败"), error_code=str(meta.get("error_code") or "preflight_failed"), blocking_component=str(meta.get("blocking_component") or "project"), recommended_action=str(meta.get("recommended_action") or "open_project"), recoverable=bool(meta.get("recoverable", True)))
                return
            provider = meta.get("provider") if isinstance(meta, dict) else None
            api_key = str(meta.get("api_key") or "") if isinstance(meta, dict) else ""
            if pipeline_run_id > 0:
                update_pipeline_run_stage(session, pipeline_run_id, status="running", current_stage=(resume_from_stage or "storyboard_plan"))
        patch_job_payload(job_id, {"project_id": pid, "candidate_batch_id": candidate_batch_id, "current_stage": resume_from_stage or "storyboard"})
        if not autopilot_stage_done(job_id, "storyboard") or resume_from_stage == "storyboard":
            run_autopilot_storyboard_stage(job_id=job_id, pid=pid, title=title, src=src, project=project, channel_key=channel_key, character_profile=character_profile, wf=wf, pack=pack, provider=provider, api_key=api_key, render_cfg=render_cfg, llm_rewrite_storyboard=llm_rewrite_storyboard, llm_generate_storyboard=llm_generate_storyboard)
            if pipeline_run_id > 0:
                with session_scope() as session:
                    update_pipeline_run_stage(session, pipeline_run_id, status="running", current_stage="audio_subtitle_finalize")
        else:
            update_job(job_id, progress=32, message="生成视频：复用已生成分镜")

        if wf == "mix" and (not autopilot_stage_done(job_id, "tts") or resume_from_stage == "tts"):
            run_autopilot_tts_stage(job_id=job_id, project_id=project_id, pid=pid, resume_from_stage=resume_from_stage, prepare_project_tts_impl=prepare_project_tts_local)
            if pipeline_run_id > 0:
                with session_scope() as session:
                    update_pipeline_run_stage(session, pipeline_run_id, status="running", current_stage="visual_resolve")
        elif wf == "mix":
            update_job(job_id, progress=40, message="生成视频：复用已定稿配音/字幕时间轴")

        if wf == "mix" and (not autopilot_stage_done(job_id, "media") or resume_from_stage == "media"):
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
            if pipeline_run_id > 0:
                with session_scope() as session:
                    update_pipeline_run_stage(session, pipeline_run_id, status="running", current_stage="render_finalize")
        elif wf == "mix":
            update_job(job_id, progress=66, message="生成视频：复用已匹配素材")
        else:
            update_job(job_id, progress=50, message="生成视频：准备渲染")
        if wf != "mix":
            autopilot_mark_stage(job_id, "media", status="done")
        run_autopilot_render_stage(job_id=job_id, project_id=project_id, pid=pid, candidate_batch_id=candidate_batch_id, resume_from_stage=resume_from_stage, render_video_impl=render_video_impl, fail_job=fail_job)
        if pipeline_run_id > 0:
            with session_scope() as session:
                update_pipeline_run_stage(session, pipeline_run_id, status="done", current_stage="render_finalize")
    except Exception as e:
        payload = autopilot_payload(job_id)
        pipeline_run_id = int(payload.get("pipeline_run_id") or 0)
        st = normalize_autopilot_stage(autopilot_resume_stage(job_id) or str(payload.get("resume_from_stage") or payload.get("current_stage") or "render").strip().lower()) or "render"
        logger.exception(
            "run_pipeline_job failed job_id={} project_id={} stage={} error={}",
            job_id,
            project_id,
            st,
            sanitize_log_text(e),
        )
        autopilot_mark_stage(job_id, st, status="failed", detail=str(e))
        recommended_action = "continue_from_project" if st in AUTOPILOT_STAGES else "open_project"
        blocking_component = "tts" if st == "tts" else "media" if st == "media" else "render" if st == "render" else "llm" if st == "storyboard" else "project"
        error_code = "tts_unavailable" if st == "tts" else "media_provider_unavailable" if st == "media" else "render_failed" if st == "render" else "storyboard_failed"
        if st == "storyboard":
            llm_code, _detail = classify_llm_failure(e)
            error_code = llm_code if llm_code != "llm_request_failed" else "storyboard_failed"
        fail_job(job_id, message=f"生成视频失败：{humanize_autopilot_detail(str(e))}", error_code=error_code, blocking_component=blocking_component, recommended_action=recommended_action, recoverable=True)
        try:
            with session_scope() as session:
                p = session.exec(select(Project).where(Project.id == int(project_id))).first()
                if p:
                    p.status = "failed"
                    p.updated_at = now_utc()
                    session.add(p)
                if pipeline_run_id > 0:
                    update_pipeline_run_stage(session, pipeline_run_id, status="failed", current_stage=st, error_code=error_code, error_detail=str(e), resume_from_stage=st)
        except Exception:
            pass
