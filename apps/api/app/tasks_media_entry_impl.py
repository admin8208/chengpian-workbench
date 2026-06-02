from __future__ import annotations


def autofill_media_local(
    job_id: int,
    project_id: int,
    prefer: str = "video",
    *,
    outer_job_id: int | None = None,
    progress_base: int = 0,
    progress_span: int = 100,
    keep_running: bool = False,
    media_impl,
) -> None:
    media_impl(
        job_id,
        project_id,
        prefer=prefer,
        outer_job_id=outer_job_id,
        progress_base=progress_base,
        progress_span=progress_span,
        keep_running=keep_running,
    )
