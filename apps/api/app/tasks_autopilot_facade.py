from __future__ import annotations

from sqlmodel import select

from app.db import session_scope
from app.models import Job, Project, Scene
from app.tasks_autopilot_bridge import (
    autopilot_get_job_status_bridge,
    autopilot_mark_stage_bridge,
    autopilot_payload_bridge,
    autopilot_resume_stage_bridge,
    autopilot_scene_stats_bridge,
    autopilot_stage_done_bridge,
    autopilot_run_local_bridge,
    save_autopilot_storyboard_bridge,
    run_autopilot_render_stage_bridge,
    run_autopilot_storyboard_stage_bridge,
)
from app.tasks_storyboard_bridge import llm_generate_storyboard_bridge, llm_rewrite_storyboard_bridge


def autopilot_payload_local(job_id: int) -> dict:
    return autopilot_payload_bridge(job_id)


def autopilot_stage_done_local(job_id: int, stage: str) -> bool:
    return autopilot_stage_done_bridge(job_id, stage)


def autopilot_resume_stage_local(job_id: int) -> str | None:
    return autopilot_resume_stage_bridge(job_id)


def autopilot_mark_stage_local(job_id: int, stage: str, *, status: str, detail: str | None = None, progress: int | None = None, message: str | None = None) -> None:
    autopilot_mark_stage_bridge(job_id, stage, status=status, detail=detail, progress=progress, message=message)


def autopilot_get_job_status_local(job_id: int) -> str:
    return autopilot_get_job_status_bridge(job_id)


def autopilot_scene_stats_local(pid: int) -> tuple[int, int, int]:
    return autopilot_scene_stats_bridge(pid)


def save_autopilot_storyboard_local(pid: int, script: str, scenes: list[dict], *, update_project_status: bool) -> bool:
    return save_autopilot_storyboard_bridge(pid, script, scenes, update_project_status=update_project_status)


def autopilot_job_guard_reason_local(job_id: int, project_id: int) -> str | None:
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


def run_autopilot_storyboard_stage_local(**kwargs) -> None:
    return run_autopilot_storyboard_stage_bridge(
        llm_rewrite_storyboard=llm_rewrite_storyboard_bridge,
        llm_generate_storyboard=llm_generate_storyboard_bridge,
        **kwargs,
    )


def run_autopilot_render_stage_local(**kwargs) -> None:
    return run_autopilot_render_stage_bridge(**kwargs)


def autopilot_run_local(**kwargs) -> None:
    return autopilot_run_local_bridge(**kwargs)


__all__ = [
    "autopilot_payload_local",
    "autopilot_stage_done_local",
    "autopilot_resume_stage_local",
    "autopilot_mark_stage_local",
    "autopilot_get_job_status_local",
    "autopilot_scene_stats_local",
    "save_autopilot_storyboard_local",
    "autopilot_job_guard_reason_local",
    "run_autopilot_storyboard_stage_local",
    "run_autopilot_render_stage_local",
    "autopilot_run_local",
]
