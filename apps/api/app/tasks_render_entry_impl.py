from __future__ import annotations

from app.jobs import abort_if_job_cancelled


def render_video_local(
    job_id: int,
    project_id: int,
    *,
    render_video_impl,
) -> None:
    if abort_if_job_cancelled(job_id):
        return
    render_video_impl(job_id, project_id, export_tag="export")
