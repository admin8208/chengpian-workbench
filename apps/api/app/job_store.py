import json
import time

from sqlalchemy.exc import OperationalError
from sqlmodel import Session, select

from app.db import session_scope
from app.models import Job
from app.projection_refresh import schedule_project_refresh
from app.time_utils import now_utc

TERMINAL_JOB_STATUSES = ("done", "failed", "cancelled")


def job_payload_obj(job: Job | None) -> dict:
    if not job:
        return {}
    try:
        payload = json.loads(job.payload_json or "{}")
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def create_job(
    kind: str,
    project_id: int,
    message: str = "",
    *,
    payload: dict | None = None,
    parent_job_id: int | None = None,
    root_job_id: int | None = None,
    retry_seq: int | None = None,
) -> Job:
    with session_scope() as session:
        job = Job(
            kind=kind,
            project_id=project_id,
            parent_job_id=(int(parent_job_id) if parent_job_id is not None and int(parent_job_id) > 0 else None),
            root_job_id=(int(root_job_id) if root_job_id is not None and int(root_job_id) > 0 else None),
            retry_seq=max(0, int(retry_seq or 0)),
            status="queued",
            progress=0,
            message=message,
            payload_json=json.dumps(payload or {}, ensure_ascii=True),
            cancel_requested=False,
            pause_requested=False,
            cancel_source="",
            cancel_reason="",
            worker_id="",
            worker_pid=0,
        )
        session.add(job)
        session.flush()
        if job.id is not None and (job.root_job_id is None or int(job.root_job_id or 0) <= 0):
            job.root_job_id = int(job.id)
            session.add(job)
            session.flush()
        session.refresh(job)
        schedule_project_refresh(session, int(job.project_id or 0))
        return job


def get_job_payload(job_id: int) -> dict:
    with session_scope() as session:
        job = session.exec(select(Job).where(Job.id == job_id)).first()
        return job_payload_obj(job)


def patch_job_payload(job_id: int, patch: dict | None = None, *, replace: bool = False) -> dict:
    with session_scope() as session:
        job = session.exec(select(Job).where(Job.id == job_id)).first()
        if not job:
            return {}
        base = {} if replace else job_payload_obj(job)
        for key, value in dict(patch or {}).items():
            if value is None:
                base.pop(str(key), None)
            else:
                base[str(key)] = value
        job.payload_json = json.dumps(base, ensure_ascii=True)
        job.updated_at = now_utc()
        session.add(job)
        schedule_project_refresh(session, int(job.project_id or 0))
        return base


def update_job(job_id: int, *, status: str | None = None, progress: int | None = None, message: str | None = None) -> None:
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            with session_scope() as session:
                update_job_in_session(session, job_id, status=status, progress=progress, message=message)
            return
        except OperationalError as exc:
            low = str(exc).lower()
            if "database is locked" not in low:
                raise
            last_err = exc
            time.sleep(0.12 * (attempt + 1))
    if last_err:
        raise last_err


def update_job_in_session(
    session: Session,
    job_id: int,
    *,
    status: str | None = None,
    progress: int | None = None,
    message: str | None = None,
) -> None:
    job = session.exec(select(Job).where(Job.id == job_id)).first()
    if not job:
        return
    if job.status == "cancelled":
        if message is not None:
            job.message = message
            job.updated_at = now_utc()
            session.add(job)
        return

    if str(job.status) == "paused" and status is not None and str(status) not in ("paused", "cancelled"):
        status = None
    heartbeat_now = now_utc()
    if status is not None:
        job.status = status
        if str(status) in TERMINAL_JOB_STATUSES:
            job.worker_id = ""
            job.worker_pid = 0
            job.worker_heartbeat_at = None
        elif str(status) == "running" and getattr(job, "worker_id", ""):
            job.worker_heartbeat_at = heartbeat_now
    if progress is not None:
        job.progress = max(0, min(100, int(progress)))
    if message is not None:
        job.message = message
    if str(job.status or "").strip().lower() == "running" and getattr(job, "worker_id", ""):
        job.worker_heartbeat_at = heartbeat_now
    job.updated_at = heartbeat_now
    session.add(job)
    schedule_project_refresh(session, int(job.project_id or 0))
