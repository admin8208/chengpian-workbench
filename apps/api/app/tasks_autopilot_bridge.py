from sqlmodel import select

from app.db import session_scope
from app.jobs import abort_if_job_cancelled, acquire_job_lease, clear_job_lease_if_terminal
from app.llm_service import get_api_key, get_default_provider
from app.models import ChannelPack, Job, LlmProvider, Project
from app.tasks_autopilot import (
    autopilot_get_job_status as autopilot_get_job_status_impl,
    autopilot_mark_stage as autopilot_mark_stage_impl,
    autopilot_payload as autopilot_payload_impl,
    autopilot_resume_stage as autopilot_resume_stage_impl,
    autopilot_run_impl,
    autopilot_scene_stats as autopilot_scene_stats_impl,
    autopilot_stage_done as autopilot_stage_done_impl,
    run_autopilot_render_stage as run_autopilot_render_stage_impl,
    run_autopilot_storyboard_stage as run_autopilot_storyboard_stage_impl,
    save_autopilot_storyboard as save_autopilot_storyboard_impl,
)
from app.tasks_autopilot_entry_impl import autopilot_run_local as autopilot_run_impl_local
from app.tasks_helpers import fail_job as _fail_job


def autopilot_payload_bridge(job_id: int) -> dict:
    return autopilot_payload_impl(job_id)


def autopilot_stage_done_bridge(job_id: int, stage: str) -> bool:
    return autopilot_stage_done_impl(job_id, stage)


def autopilot_resume_stage_bridge(job_id: int) -> str | None:
    return autopilot_resume_stage_impl(job_id)


def autopilot_mark_stage_bridge(job_id: int, stage: str, *, status: str, detail: str | None = None, progress: int | None = None, message: str | None = None) -> None:
    autopilot_mark_stage_impl(job_id, stage, status=status, detail=detail, progress=progress, message=message)


def autopilot_get_job_status_bridge(job_id: int) -> str:
    return autopilot_get_job_status_impl(job_id)


def autopilot_scene_stats_bridge(pid: int) -> tuple[int, int, int]:
    return autopilot_scene_stats_impl(pid)


def save_autopilot_storyboard_bridge(pid: int, script: str, scenes: list[dict], *, update_project_status: bool) -> bool:
    return save_autopilot_storyboard_impl(pid, script, scenes, update_project_status=update_project_status)


def run_autopilot_storyboard_stage_bridge(*, llm_rewrite_storyboard, llm_generate_storyboard, **kwargs) -> None:
    return run_autopilot_storyboard_stage_impl(**kwargs, llm_rewrite_storyboard=llm_rewrite_storyboard, llm_generate_storyboard=llm_generate_storyboard)


def run_autopilot_render_stage_bridge(*, render_video_impl, **kwargs) -> None:
    return run_autopilot_render_stage_impl(**kwargs, render_video_impl=render_video_impl, fail_job=_fail_job)


def autopilot_job_guard_reason_bridge(job_id: int, project_id: int) -> str | None:
    try:
        jid = int(job_id)
        pid = int(project_id)
    except Exception:
        return "invalid_args"
    if jid <= 0 or pid <= 0:
        return "invalid_args"
    with session_scope() as session:
        job = session.exec(select(Job).where(Job.id == jid)).first()
        if not job:
            return "missing_job"
        if str(getattr(job, "kind", "") or "").strip().lower() != "autopilot":
            return "job_kind_mismatch"
        if int(getattr(job, "project_id", 0) or 0) != pid:
            return "project_mismatch"
        project = session.exec(select(Project).where(Project.id == pid)).first()
        if not project:
            return "missing_project"
        status = str(getattr(job, "status", "") or "").strip().lower()
        if status in ("done", "failed", "cancelled"):
            return f"terminal_job:{status}"
    return None


def autopilot_run_local_bridge(job_id: int, project_id: int, *, llm_generate_storyboard, llm_rewrite_storyboard, render_video_impl, autofill_media_local, generate_images_local) -> None:
    autopilot_run_impl_local(
        job_id,
        project_id,
        guard_reason_fn=autopilot_job_guard_reason_bridge,
        acquire_job_lease=acquire_job_lease,
        clear_job_lease_if_terminal=clear_job_lease_if_terminal,
        abort_if_job_cancelled=abort_if_job_cancelled,
        autopilot_run_impl=autopilot_run_impl,
        fail_job=_fail_job,
        llm_generate_storyboard=llm_generate_storyboard,
        llm_rewrite_storyboard=llm_rewrite_storyboard,
        render_video_impl=render_video_impl,
        autofill_media_local=autofill_media_local,
        generate_images_local=generate_images_local,
        get_default_provider=get_default_provider,
        get_api_key=get_api_key,
    )
