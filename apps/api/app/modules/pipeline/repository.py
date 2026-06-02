from __future__ import annotations

from sqlmodel import Session, select

from app.models import Project
from app.models_revisions import PipelineRun
from app.time_utils import now_utc


def create_pipeline_run(
    session: Session,
    *,
    project: Project,
    baseline_revision_id: int | None,
    storyboard_revision_id: int | None,
    current_stage: str,
) -> PipelineRun:
    if project.id is None:
        raise ValueError("project id is required")
    run = PipelineRun(
        project_id=int(project.id),
        baseline_revision_id=baseline_revision_id,
        storyboard_revision_id=storyboard_revision_id,
        status="queued",
        current_stage=str(current_stage or "storyboard_plan"),
        started_at=now_utc(),
    )
    session.add(run)
    session.flush()
    session.refresh(run)
    project.current_pipeline_run_id = int(run.id) if run.id is not None else None
    project.updated_at = now_utc()
    session.add(project)
    return run


def update_pipeline_run_stage(session: Session, run_id: int, *, status: str, current_stage: str, current_substage: str = "", error_code: str = "", error_detail: str = "", resume_from_stage: str = "") -> None:
    run = session.exec(select(PipelineRun).where(PipelineRun.id == int(run_id))).first()
    if not run:
        return
    run.status = status
    run.current_stage = current_stage
    run.current_substage = current_substage
    run.error_code = error_code
    run.error_detail = error_detail
    run.resume_from_stage = resume_from_stage
    run.updated_at = now_utc()
    if status in ("done", "failed", "cancelled"):
        run.finished_at = now_utc()
    session.add(run)


def fail_pipeline_run(session: Session, run_id: int | None, *, message: str = "") -> None:
    if not run_id:
        return
    run = session.exec(select(PipelineRun).where(PipelineRun.id == int(run_id))).first()
    if not run:
        return
    run.status = "failed"
    run.error_code = "enqueue_failed"
    run.error_detail = str(message or "任务入队失败")
    run.finished_at = now_utc()
    run.updated_at = now_utc()
    session.add(run)
    project = session.exec(select(Project).where(Project.id == int(run.project_id))).first()
    if project and getattr(project, "current_pipeline_run_id", None) == int(run.id):
        project.current_pipeline_run_id = None
        project.updated_at = now_utc()
        session.add(project)


def get_pipeline_run(session: Session, run_id: int | None) -> PipelineRun | None:
    if not run_id:
        return None
    return session.exec(select(PipelineRun).where(PipelineRun.id == int(run_id))).first()
