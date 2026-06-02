from datetime import timedelta

from sqlmodel import select

from app.db import session_scope
from app.job_control import job_lease_is_stale
from app.models import Job
from app.time_utils import now_utc

JOB_LEASE_STALE_MINUTES = 10


def recover_abandoned_jobs(*, stale_minutes: int = JOB_LEASE_STALE_MINUTES) -> int:
    now = now_utc()
    now_ts = now.timestamp()
    stale_seconds = int(timedelta(minutes=max(1, int(stale_minutes or JOB_LEASE_STALE_MINUTES))).total_seconds())
    changed = 0
    with session_scope() as session:
        rows = session.exec(select(Job).where(Job.status == "running").order_by(Job.updated_at.asc(), Job.created_at.asc())).all()
        for job in rows:
            if not job_lease_is_stale(job, stale_seconds=stale_seconds, now=now):
                continue
            job.status = "failed"
            job.progress = 100
            job.message = "任务中断：worker 心跳超时，已标记失败，可从项目继续生成"
            job.worker_id = ""
            job.worker_pid = 0
            job.worker_heartbeat_at = None
            job.updated_at = now
            session.add(job)
            changed += 1
    return changed
