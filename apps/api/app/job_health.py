from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import select

from app.db import session_scope
from app.health_checks import check_huey_queue, check_worker
from app.job_control import reconcile_stale_job_in_session
from app.models import Job


def reconcile_stale_jobs_before_dispatch(limit: int = 50) -> None:
    try:
        with session_scope() as session:
            rows = session.exec(
                select(Job)
                .where(Job.status.in_(["running", "queued", "paused"]))
                .order_by(Job.updated_at.desc(), Job.created_at.desc())
                .limit(max(1, int(limit or 50)))
            ).all()
            for job in rows:
                reconcile_stale_job_in_session(session, job)
    except Exception:
        return


def ensure_job_dispatch_ready() -> None:
    reconcile_stale_jobs_before_dispatch()
    queue = check_huey_queue()
    if not bool(getattr(queue, "ok", False)):
        detail = str(getattr(queue, "detail", "") or "")[:300]
        raise HTTPException(
            status_code=503,
            detail=f"后台任务队列不可用，请先检查 Redis/Huey 服务。{detail}".strip(),
        )

    worker = check_worker()
    if not bool(getattr(worker, "ok", False)):
        detail = str(getattr(worker, "detail", "") or "")[:300]
        hint = str(getattr(worker, "hint", "") or "")[:300]
        suffix = f"{detail} {hint}".strip()
        raise HTTPException(
            status_code=503,
            detail=f"后台任务 Worker 未就绪，任务尚不能启动。{suffix}".strip(),
        )
