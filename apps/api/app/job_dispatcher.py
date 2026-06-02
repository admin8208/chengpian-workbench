from __future__ import annotations

from collections.abc import Callable

from fastapi import HTTPException

from app.api_common import job_out
from app.job_health import ensure_job_dispatch_ready
from app.jobs import create_job, ensure_enqueued, mark_job_enqueue_failed
from app.schemas import JobOut


EnqueueFunc = Callable[[int], object]


def enqueue_project_job(
    *,
    kind: str,
    project_id: int,
    message: str,
    payload: dict | None,
    enqueue: EnqueueFunc,
    enqueue_error_message: str,
    parent_job_id: int | None = None,
    root_job_id: int | None = None,
    retry_seq: int | None = None,
) -> JobOut:
    ensure_job_dispatch_ready()
    job = create_job(
        kind,
        project_id,
        message=message,
        payload=payload,
        parent_job_id=parent_job_id,
        root_job_id=root_job_id,
        retry_seq=retry_seq,
    )
    if job.id is None:
        raise HTTPException(status_code=500, detail="创建任务失败")

    try:
        result = enqueue(int(job.id))
    except Exception as exc:
        mark_job_enqueue_failed(int(job.id), message=f"{enqueue_error_message}：{exc}")
        raise HTTPException(status_code=500, detail=enqueue_error_message)

    try:
        ensure_enqueued(result, error_message=enqueue_error_message)
    except RuntimeError as exc:
        mark_job_enqueue_failed(int(job.id), message=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))

    return job_out(int(job.id))
