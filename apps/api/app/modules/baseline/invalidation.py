from __future__ import annotations

from sqlmodel import Session, select

from app.models import Project
from app.models_revisions import AudioSubtitleRevision, ContentBaselineRevision, PipelineRun, StoryboardRevision
from app.time_utils import now_utc


def invalidate_confirmed_baseline_chain(session: Session, project: Project) -> None:
    if project.id is None:
        return
    project_id = int(project.id)
    confirmed_id = int(getattr(project, "confirmed_baseline_revision_id", 0) or 0)
    if confirmed_id > 0:
        confirmed_rows = session.exec(
            select(ContentBaselineRevision).where(
                ContentBaselineRevision.project_id == project_id,
                ContentBaselineRevision.id == confirmed_id,
            )
        ).all()
        for row in confirmed_rows:
            row.status = "superseded"
            row.updated_at = now_utc()
            session.add(row)
    storyboard_rows = session.exec(
        select(StoryboardRevision).where(
            StoryboardRevision.project_id == project_id,
            StoryboardRevision.status == "ready",
        )
    ).all()
    for row in storyboard_rows:
        row.status = "stale"
        row.updated_at = now_utc()
        session.add(row)
    audio_rows = session.exec(
        select(AudioSubtitleRevision).where(
            AudioSubtitleRevision.project_id == project_id,
            AudioSubtitleRevision.status == "ready",
        )
    ).all()
    for row in audio_rows:
        row.status = "stale"
        row.updated_at = now_utc()
        session.add(row)
    pipeline_rows = session.exec(
        select(PipelineRun).where(
            PipelineRun.project_id == project_id,
            PipelineRun.status.in_(["queued", "running"]),
        )
    ).all()
    for row in pipeline_rows:
        row.status = "failed"
        row.error_code = "baseline_invalidated"
        row.error_detail = "confirmed baseline changed"
        row.resume_from_stage = "storyboard"
        row.finished_at = now_utc()
        row.updated_at = now_utc()
        session.add(row)
    project.confirmed_baseline_revision_id = None
    project.current_pipeline_run_id = None
    project.updated_at = now_utc()
    session.add(project)
