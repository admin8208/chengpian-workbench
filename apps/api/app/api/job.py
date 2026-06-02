"""Job router extracted from the main application entrypoint."""

from fastapi import APIRouter, Query

from app.application.jobs import (
    batch_get_jobs_api,
    cancel_job_api,
    delete_job_api,
    get_job_api,
    list_jobs_api,
    pause_job_api,
    resume_job_api,
    retry_job_api,
)
from app.schemas import JobCreateOut, JobOut, OkOut

router = APIRouter(tags=["job"])


@router.get("/api/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int):
    return get_job_api(job_id)


@router.get("/api/jobs", response_model=list[JobOut])
def list_jobs(limit: int = 100, project_id: int = 0):
    return list_jobs_api(limit, project_id=project_id)


@router.get("/api/jobs/batch", response_model=list[JobOut])
def batch_get_jobs(ids: str = Query(..., description="逗号分隔的 Job ID 列表")):
    """批量获取 Job 状态，减少轮询请求数量。"""
    job_ids = [int(x.strip()) for x in ids.split(",") if x.strip().isdigit()]
    return batch_get_jobs_api(job_ids)


@router.post("/api/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: int):
    return cancel_job_api(job_id)


@router.post("/api/jobs/{job_id}/pause", response_model=JobOut)
def pause_one_job(job_id: int):
    return pause_job_api(job_id)


@router.post("/api/jobs/{job_id}/resume", response_model=JobOut)
def resume_one_job(job_id: int):
    return resume_job_api(job_id)


@router.post("/api/jobs/{job_id}/retry", response_model=JobCreateOut)
def retry_job(job_id: int):
    return retry_job_api(job_id)


@router.delete("/api/jobs/{job_id}", response_model=OkOut)
def delete_job(job_id: int):
    return delete_job_api(job_id)
