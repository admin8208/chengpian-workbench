import json

from sqlalchemy import desc
from sqlmodel import Session, select

from app.job_control import finalize_cancelled_job_if_stale_in_session, reconcile_stale_job_in_session
from app.models import Job, Project
from app.modules.pipeline.repository import get_pipeline_run
from app.modules.pipeline.state import pipeline_continue_stage, pipeline_stage_label
from app.models_revisions import PipelineRun


def project_autopilot_mode(p: Project) -> str:
    return "balanced"


def latest_autopilot_job(session: Session, project_id: int, *, active_only: bool = False) -> Job | None:
    query = select(Job).where(Job.project_id == int(project_id)).where(Job.kind == "autopilot")
    if active_only:
        query = query.where(Job.status.in_(["queued", "running", "paused"]))
    return session.exec(query.order_by(Job.created_at.desc())).first()


def autopilot_continue_stage(payload: dict | None = None, run: PipelineRun | None = None) -> str | None:
    return pipeline_continue_stage(run, payload)


def get_project_workflow_meta(session: Session, project: Project) -> dict:
    active_autopilot_jobs = session.exec(
        select(Job)
        .where(Job.project_id == int(project.id or 0))
        .where(Job.kind == "autopilot")
        .where(Job.status.in_(["queued", "running", "paused"]))
        .order_by(desc(Job.created_at))
    ).all()
    for active in active_autopilot_jobs:
        if getattr(active, "id", None) is not None:
            finalize_cancelled_job_if_stale_in_session(session, int(active.id))
            reconcile_stale_job_in_session(session, active)

    latest_job = session.exec(select(Job).where(Job.project_id == int(project.id or 0)).order_by(desc(Job.created_at))).first()
    active_job = session.exec(
        select(Job)
        .where(Job.project_id == int(project.id or 0))
        .where(Job.status.in_(["queued", "running", "paused"]))
        .order_by(desc(Job.created_at))
    ).first()
    latest_ap = latest_autopilot_job(session, int(project.id or 0), active_only=False)
    active_ap = latest_autopilot_job(session, int(project.id or 0), active_only=True)
    summary_job = active_job or active_ap or latest_ap or latest_job
    payload: dict = {}
    try:
        payload = json.loads(getattr(summary_job, "payload_json", "{}") or "{}") if summary_job else {}
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}
    pipeline_run = get_pipeline_run(session, getattr(project, "current_pipeline_run_id", None))
    stage = pipeline_stage_label(pipeline_run, payload)
    continue_stage = pipeline_continue_stage(pipeline_run, payload)
    next_action = "open_project"
    status = str(getattr(pipeline_run, "status", "") or getattr(summary_job, "status", "") or "") or None
    if status == "failed" and continue_stage:
        next_action = "continue_autopilot"
    elif status in ("queued", "running", "paused"):
        next_action = "view_progress"
    elif str(project.status or "") == "ready":
        next_action = "view_final"
    return {
        "workflow_stage": stage,
        "continue_stage": continue_stage,
        "active_job_status": status,
        "next_action": next_action,
        "summary_job": summary_job,
    }
