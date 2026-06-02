import json
from datetime import datetime

from sqlmodel import select

from app.db import session_scope
from app.models import JobCenterProjection, ProjectCenterProjection
from app.time_utils import now_utc

PROJECT_JOB_KINDS = ("autopilot", "autofill_media", "images", "scene_image", "render", "script_prepare")
ACTIVE_JOB_STATUSES = ("queued", "running", "paused")


def _parse_cursor(cursor: str) -> datetime | None:
    if not cursor:
        return None
    try:
        return datetime.fromisoformat(str(cursor).replace('Z', '+00:00'))
    except Exception:
        return None


def upsert_project_projection(project_id: int, payload: dict) -> None:
    with session_scope() as session:
        row = session.exec(select(ProjectCenterProjection).where(ProjectCenterProjection.project_id == int(project_id))).first()
        if not row:
            row = ProjectCenterProjection(project_id=int(project_id))
        row.payload_json = json.dumps(payload, ensure_ascii=True)
        row.updated_at = now_utc()
        session.add(row)


def delete_project_projection(project_id: int) -> None:
    with session_scope() as session:
        row = session.exec(select(ProjectCenterProjection).where(ProjectCenterProjection.project_id == int(project_id))).first()
        if row:
            session.delete(row)


def replace_job_projections(project_id: int, items: list[dict]) -> None:
    with session_scope() as session:
        rows = session.exec(select(JobCenterProjection).where(JobCenterProjection.project_id == int(project_id))).all()
        for row in rows:
            session.delete(row)
        updated_at = now_utc()
        for item in items:
            entry_key = str(item.get('entry_key') or '').strip()
            if not entry_key:
                continue
            session.add(JobCenterProjection(
                entry_key=entry_key,
                project_id=int(project_id),
                job_kind=str(item.get('job_kind') or '').strip().lower(),
                status=str(item.get('status') or '').strip().lower(),
                is_active=bool(item.get('is_active')),
                payload_json=json.dumps(item, ensure_ascii=True),
                updated_at=updated_at,
            ))


def delete_job_projections(project_id: int) -> None:
    with session_scope() as session:
        rows = session.exec(select(JobCenterProjection).where(JobCenterProjection.project_id == int(project_id))).all()
        for row in rows:
            session.delete(row)


def load_project_projection_rows(*, limit: int | None = None, cursor: str = '') -> list[ProjectCenterProjection]:
    with session_scope() as session:
        query = select(ProjectCenterProjection)
        cursor_dt = _parse_cursor(cursor)
        if cursor_dt:
            query = query.where(ProjectCenterProjection.updated_at < cursor_dt)
        query = query.order_by(ProjectCenterProjection.updated_at.desc())
        if limit is not None and limit > 0:
            query = query.limit(int(limit))
        return session.exec(query).all()


def load_job_projection_rows(*, project_id: int = 0, scope: str = 'project', status: str = 'all', limit: int | None = None, cursor: str = '') -> list[JobCenterProjection]:
    with session_scope() as session:
        query = select(JobCenterProjection)
        if project_id > 0:
            query = query.where(JobCenterProjection.project_id == int(project_id))
        if str(scope or '').strip().lower() == 'project':
            query = query.where(JobCenterProjection.job_kind.in_(PROJECT_JOB_KINDS))
        normalized_status = str(status or '').strip().lower()
        if normalized_status == 'active':
            query = query.where(JobCenterProjection.is_active == True)  # noqa: E712
        elif normalized_status in {'failed', 'done', 'cancelled'}:
            query = query.where(JobCenterProjection.status == normalized_status)
        cursor_dt = _parse_cursor(cursor)
        if cursor_dt:
            query = query.where(JobCenterProjection.updated_at < cursor_dt)
        query = query.order_by(JobCenterProjection.updated_at.desc())
        if limit is not None and limit > 0:
            query = query.limit(int(limit))
        return session.exec(query).all()
