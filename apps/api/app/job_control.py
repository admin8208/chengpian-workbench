import json
import os
import time
from datetime import datetime

from sqlmodel import Session, select

from app.db import session_scope
from app.job_store import TERMINAL_JOB_STATUSES, update_job
from app.models import Job
from app.models_revisions import PipelineRun
from app.modules.pipeline.repository import get_pipeline_run, update_pipeline_run_stage
from app.time_utils import now_utc


JOB_LEASE_STALE_SECONDS = 120


def _safe_age_seconds(dt: datetime | None, now: datetime | None = None) -> int | None:
    if dt is None:
        return None
    cur = now or now_utc()
    try:
        return max(0, int((cur - dt).total_seconds()))
    except Exception:
        return None


def worker_pid_exists(pid: int) -> bool:
    try:
        worker_pid = int(pid or 0)
    except Exception:
        worker_pid = 0
    if worker_pid <= 0:
        return False
    try:
        os.kill(worker_pid, 0)
        return True
    except OSError:
        return False
    except Exception:
        return False


def job_lease_age_seconds(job: Job, *, now: datetime | None = None) -> int | None:
    heartbeat_at = getattr(job, "worker_heartbeat_at", None)
    if heartbeat_at is not None:
        return _safe_age_seconds(heartbeat_at, now=now)
    updated_at = getattr(job, "updated_at", None)
    if updated_at is not None:
        return _safe_age_seconds(updated_at, now=now)
    return _safe_age_seconds(getattr(job, "created_at", None), now=now)


def job_lease_is_stale(job: Job, *, stale_seconds: int = JOB_LEASE_STALE_SECONDS, now: datetime | None = None) -> bool:
    status = str(getattr(job, "status", "") or "").strip().lower()
    if status != "running":
        return False
    current = now or now_utc()
    worker_pid = int(getattr(job, "worker_pid", 0) or 0)
    if worker_pid > 0 and not worker_pid_exists(worker_pid):
        return True
    age_seconds = job_lease_age_seconds(job, now=current)
    if age_seconds is None:
        return True
    return age_seconds >= max(30, int(stale_seconds or JOB_LEASE_STALE_SECONDS))


def reconcile_stale_job_in_session(session: Session, job: Job, *, stale_seconds: int = JOB_LEASE_STALE_SECONDS) -> bool:
    if not job:
        return False
    status = str(getattr(job, "status", "") or "").strip().lower()
    if status in TERMINAL_JOB_STATUSES:
        return False
    if bool(getattr(job, "cancel_requested", False)) and job_lease_is_stale(job, stale_seconds=stale_seconds):
        now = now_utc()
        job.status = "cancelled"
        job.progress = 100
        job.message = str(job.message or "").strip() or "已取消"
        job.worker_id = ""
        job.worker_pid = 0
        job.worker_heartbeat_at = None
        job.updated_at = now
        session.add(job)
        project_id = int(getattr(job, "project_id", 0) or 0)
        if project_id > 0:
            run = _active_pipeline_run_for_project(session, project_id)
            if run is not None and _pipeline_run_matches_job(run, job):
                update_pipeline_run_stage(session, int(run.id), status="cancelled", current_stage=str(getattr(run, "current_stage", "") or "render"))
        return True
    if status == "running" and job_lease_is_stale(job, stale_seconds=stale_seconds):
        now = now_utc()
        job.status = "failed"
        job.progress = 100
        job.message = "任务中断：worker 租约失效，可从项目继续生成"
        job.worker_id = ""
        job.worker_pid = 0
        job.worker_heartbeat_at = None
        job.updated_at = now
        session.add(job)
        project_id = int(getattr(job, "project_id", 0) or 0)
        if project_id > 0:
            run = _active_pipeline_run_for_project(session, project_id)
            if run is not None and _pipeline_run_matches_job(run, job):
                update_pipeline_run_stage(session, int(run.id), status="failed", current_stage=str(getattr(run, "current_stage", "") or "render"))
        return True
    return False


def is_job_cancelled(job_id: int) -> bool:
    with session_scope() as session:
        job = session.exec(select(Job).where(Job.id == job_id)).first()
        return bool(job and (bool(getattr(job, "cancel_requested", False)) or job.status == "cancelled"))


def abort_if_job_cancelled(job_id: int, *, message: str = "已取消") -> bool:
    if not is_job_cancelled(job_id):
        return False
    try:
        update_job(job_id, status="cancelled", progress=100, message=message)
    except Exception:
        pass
    return True


def is_job_cancelled_in_session(session: Session, job_id: int) -> bool:
    job = session.exec(select(Job).where(Job.id == job_id)).first()
    return bool(job and (bool(getattr(job, "cancel_requested", False)) or str(job.status) == "cancelled"))


def finalize_cancelled_job_if_stale(job_id: int) -> bool:
    with session_scope() as session:
        return finalize_cancelled_job_if_stale_in_session(session, job_id)


def finalize_cancelled_job_if_stale_in_session(session: Session, job_id: int) -> bool:
    job = session.exec(select(Job).where(Job.id == int(job_id))).first()
    if not job:
        return False
    status = str(job.status or "").strip().lower()
    if status in TERMINAL_JOB_STATUSES:
        return False
    if not bool(getattr(job, "cancel_requested", False)):
        return False
    return reconcile_stale_job_in_session(session, job)


def _active_pipeline_run_for_project(session: Session, project_id: int) -> PipelineRun | None:
    rows = session.exec(
        select(PipelineRun)
        .where(PipelineRun.project_id == int(project_id))
        .where(PipelineRun.status.in_(["queued", "running"]))
        .order_by(PipelineRun.updated_at.desc(), PipelineRun.created_at.desc())
    ).all()
    return rows[0] if rows else None


def _pipeline_run_matches_job(run: PipelineRun, job: Job) -> bool:
    try:
        payload = json.loads(getattr(job, "payload_json", "{}") or "{}")
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}
    run_id = int(payload.get("pipeline_run_id") or 0)
    return bool(run_id > 0 and getattr(run, "id", None) is not None and int(run.id) == run_id)


def request_job_cancel(job_id: int, *, source: str = "api", reason: str = "") -> bool:
    with session_scope() as session:
        job = session.exec(select(Job).where(Job.id == int(job_id))).first()
        if not job:
            return False
        status = str(job.status or "").strip().lower()
        if status in TERMINAL_JOB_STATUSES:
            return False
        job.cancel_source = str(source or "api")[:80]
        job.cancel_reason = str(reason or "")[:300]
        if status == "queued":
            job.status = "cancelled"
            job.progress = 100
            job.message = "已取消"
            job.worker_id = ""
            job.worker_pid = 0
            job.worker_heartbeat_at = None
        else:
            job.cancel_requested = True
            job.message = "正在请求取消" + (f"：{reason}" if reason else "")
        job.updated_at = now_utc()
        session.add(job)
        finalize_cancelled_job_if_stale_in_session(session, int(job_id))
        return True


def acquire_job_lease(job_id: int, *, worker_id: str | None = None, pid: int | None = None) -> bool:
    wid = str(worker_id or f"worker-{os.getpid()}")[:120]
    worker_pid = int(pid if pid is not None else os.getpid())
    with session_scope() as session:
        job = session.exec(select(Job).where(Job.id == int(job_id))).first()
        if not job:
            return False
        status = str(job.status or "").strip().lower()
        if status in TERMINAL_JOB_STATUSES or bool(getattr(job, "cancel_requested", False)):
            return False
        now = now_utc()
        job.status = "running"
        job.worker_id = wid
        job.worker_pid = worker_pid
        job.worker_started_at = now
        job.worker_heartbeat_at = now
        job.updated_at = now
        session.add(job)
        return True


def touch_job_lease(job_id: int) -> None:
    with session_scope() as session:
        job = session.exec(select(Job).where(Job.id == int(job_id))).first()
        if not job:
            return
        if str(job.status or "").strip().lower() != "running":
            return
        now = now_utc()
        job.worker_heartbeat_at = now
        job.updated_at = now
        session.add(job)


def clear_job_lease_if_terminal(job_id: int) -> None:
    with session_scope() as session:
        job = session.exec(select(Job).where(Job.id == int(job_id))).first()
        if not job:
            return
        if str(job.status or "").strip().lower() not in TERMINAL_JOB_STATUSES:
            return
        job.worker_id = ""
        job.worker_pid = 0
        job.worker_heartbeat_at = None
        job.updated_at = now_utc()
        session.add(job)


def is_job_paused(job_id: int) -> bool:
    with session_scope() as session:
        job = session.exec(select(Job).where(Job.id == job_id)).first()
        return bool(job and str(job.status) == "paused")


def is_job_paused_in_session(session: Session, job_id: int) -> bool:
    job = session.exec(select(Job).where(Job.id == job_id)).first()
    return bool(job and str(job.status) == "paused")


def pause_job(job_id: int) -> None:
    with session_scope() as session:
        job = session.exec(select(Job).where(Job.id == job_id)).first()
        if not job:
            return
        if str(job.status) in ("done", "failed", "cancelled"):
            return
        try:
            payload = json.loads(job.payload_json or "{}")
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload["paused_prev_status"] = str(job.status or "queued")
        job.payload_json = json.dumps(payload, ensure_ascii=True)
        job.status = "paused"
        job.message = "已暂停"
        job.updated_at = now_utc()
        session.add(job)


def resume_job(job_id: int) -> None:
    with session_scope() as session:
        job = session.exec(select(Job).where(Job.id == job_id)).first()
        if not job:
            return
        if str(job.status) != "paused":
            return

        prev = "running"
        try:
            payload = json.loads(job.payload_json or "{}")
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            prev = str(payload.get("paused_prev_status") or "running")
            payload.pop("paused_prev_status", None)
            job.payload_json = json.dumps(payload, ensure_ascii=True)

        if prev not in ("queued", "running"):
            prev = "running"
        job.status = prev
        job.message = "已继续"
        job.updated_at = now_utc()
        session.add(job)


def wait_if_job_paused(
    job_id: int,
    *,
    poll_s: float = 0.4,
    heartbeat_s: float = 4.0,
    message: str = "已暂停（可在任务里继续）",
) -> None:
    last_beat = 0.0
    while True:
        if is_job_cancelled(job_id):
            return
        if not is_job_paused(job_id):
            return
        now = time.time()
        if (now - last_beat) >= float(heartbeat_s or 0):
            try:
                update_job(job_id, message=message)
            except Exception:
                pass
            last_beat = now
        time.sleep(max(0.15, min(2.0, float(poll_s or 0.4))))
