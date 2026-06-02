from app.job_store import update_job


def huey_queue_table_count() -> int | None:
    try:
        from app.huey_app import huey

        return int(huey.pending_count())
    except Exception:
        return None


def ensure_enqueued(result, *, error_message: str) -> None:
    task_id = getattr(result, "id", None)
    if task_id:
        return
    if result is not None:
        return
    raise RuntimeError(str(error_message or "任务入队失败，请检查后台任务服务"))


def mark_job_enqueue_failed(job_id: int, *, message: str) -> None:
    update_job(int(job_id), status="failed", progress=100, message=str(message or "任务入队失败，请检查后台任务服务"))
