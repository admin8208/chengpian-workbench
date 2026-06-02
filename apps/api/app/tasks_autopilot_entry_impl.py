from __future__ import annotations

from loguru import logger


def autopilot_run_local(
    job_id: int,
    project_id: int,
    *,
    guard_reason_fn,
    acquire_job_lease,
    clear_job_lease_if_terminal,
    abort_if_job_cancelled,
    autopilot_run_impl,
    fail_job,
    llm_generate_storyboard,
    llm_rewrite_storyboard,
    render_video_impl,
    autofill_media_local,
    generate_images_local,
    get_default_provider,
    get_api_key,
) -> None:
    guard_reason = guard_reason_fn(job_id, project_id)
    if guard_reason:
        logger.warning("skip orphaned autopilot task job_id={} project_id={} reason={}", job_id, project_id, guard_reason)
        return
    if not acquire_job_lease(job_id):
        logger.warning("skip autopilot task without lease job_id={} project_id={}", job_id, project_id)
        return
    try:
        if abort_if_job_cancelled(job_id):
            return
        autopilot_run_impl(
            job_id,
            project_id,
            fail_job=fail_job,
            llm_generate_storyboard=llm_generate_storyboard,
            llm_rewrite_storyboard=llm_rewrite_storyboard,
            render_video_impl=render_video_impl,
            autofill_media_local=autofill_media_local,
            generate_images_local=generate_images_local,
            get_default_provider=get_default_provider,
            get_api_key=get_api_key,
        )
    finally:
        clear_job_lease_if_terminal(job_id)
