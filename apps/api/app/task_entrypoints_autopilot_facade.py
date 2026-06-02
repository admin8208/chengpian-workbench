from __future__ import annotations

from app.tasks_image_bridge import generate_project_images_local_bridge as generate_project_images_local
from app.tasks_media_bridge import autofill_media_local_bridge as autofill_media_local
from app.tasks_autopilot_bridge import autopilot_run_local_bridge
from app.tasks_render_facade import render_video_impl_local
from app.tasks_storyboard_bridge import llm_generate_storyboard_bridge, llm_rewrite_storyboard_bridge


def autopilot_run_local(job_id: int, project_id: int) -> None:
    autopilot_run_local_bridge(
        job_id,
        project_id,
        llm_generate_storyboard=llm_generate_storyboard_bridge,
        llm_rewrite_storyboard=llm_rewrite_storyboard_bridge,
        render_video_impl=render_video_impl_local,
        autofill_media_local=autofill_media_local,
        generate_images_local=generate_project_images_local,
    )


__all__ = ["autopilot_run_local"]
