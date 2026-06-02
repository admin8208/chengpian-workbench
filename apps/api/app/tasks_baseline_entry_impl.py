from __future__ import annotations

from loguru import logger

from app.jobs import abort_if_job_cancelled, update_job, wait_if_job_paused
from app.logging_setup import sanitize_log_text


def prepare_project_script_local(
    job_id: int,
    project_id: int,
    *,
    prepare_script_fn,
    abort_if_job_cancelled_fn=abort_if_job_cancelled,
    update_job_fn=update_job,
    wait_if_job_paused_fn=wait_if_job_paused,
) -> None:
    if abort_if_job_cancelled_fn(job_id):
        return
    update_job_fn(job_id, status="running", progress=1, message="正在生成文案草稿")
    wait_if_job_paused_fn(job_id)
    try:
        update_job_fn(job_id, progress=20, message="分析项目输入")
        prepare_script_fn(project_id)
        update_job_fn(job_id, status="done", progress=100, message="文案草稿已生成")
    except Exception as exc:
        logger.exception("prepare_project_script failed job_id={} project_id={} error={}", job_id, project_id, sanitize_log_text(exc))
        update_job_fn(job_id, status="failed", progress=100, message=f"生成文案失败：{exc}")
