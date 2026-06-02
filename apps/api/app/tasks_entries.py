from __future__ import annotations

from app.huey_app import huey
from app.modules.baseline.task_service import prepare_project_script_task
from app.task_entrypoints_autopilot_facade import autopilot_run_local
from app.tasks_baseline_entry_impl import prepare_project_script_local
from app.tasks_image_bridge import generate_project_images_local_bridge as generate_project_images_local
from app.tasks_image_bridge import generate_scene_image_local_bridge as generate_scene_image_local
from app.tasks_media_bridge import autofill_media_local_bridge as autofill_media_local
from app.tasks_render_entry_impl import render_video_local as render_video_local_entry_impl
from app.tasks_render_facade import render_video_impl_local
from app.tasks_storyboard_bridge import generate_storyboard_local_bridge as generate_storyboard_local
from app.tasks_storyboard_bridge import rewrite_storyboard_local_bridge as rewrite_storyboard_local


def render_video_local(job_id: int, project_id: int) -> None:
    render_video_local_entry_impl(job_id, project_id, render_video_impl=render_video_impl_local)


@huey.task()
def autopilot_run(job_id: int, project_id: int) -> None:
    autopilot_run_local(job_id, project_id)


@huey.task()
def prepare_project_script(job_id: int, project_id: int) -> None:
    prepare_project_script_local(job_id, project_id, prepare_script_fn=prepare_project_script_task)


@huey.task()
def rewrite_storyboard(job_id: int, project_id: int, *, level: str = "medium") -> None:
    rewrite_storyboard_local(job_id, project_id, level=level)


@huey.task()
def generate_storyboard(job_id: int, project_id: int, *, topic: str | None = None) -> None:
    generate_storyboard_local(job_id, project_id, topic=topic)


@huey.task()
def render_video(job_id: int, project_id: int) -> None:
    render_video_local(job_id, project_id)


@huey.task()
def autofill_media(
    job_id: int,
    project_id: int,
    prefer: str = "video",
    *,
    outer_job_id: int | None = None,
    progress_base: int = 0,
    progress_span: int = 100,
    keep_running: bool = False,
) -> None:
    autofill_media_local(
        job_id,
        project_id,
        prefer=prefer,
        outer_job_id=outer_job_id,
        progress_base=progress_base,
        progress_span=progress_span,
        keep_running=keep_running,
    )


@huey.task()
def generate_project_images(
    job_id: int,
    project_id: int,
    *,
    force: bool = False,
    manage_job_state: bool = True,
) -> None:
    return _call_generate_project_images_local(job_id, project_id, force=force, manage_job_state=manage_job_state)


@huey.task()
def generate_scene_image(
    job_id: int,
    scene_id: int,
    *,
    force: bool = True,
    manage_job_state: bool = True,
) -> None:
    return _call_generate_scene_image_local(job_id, scene_id, force=force, manage_job_state=manage_job_state)


def _call_generate_project_images_local(job_id: int, project_id: int, *, force: bool, manage_job_state: bool) -> None:
    return generate_project_images_local(job_id, project_id, force=force, manage_job_state=manage_job_state)


def _call_generate_scene_image_local(job_id: int, scene_id: int, *, force: bool, manage_job_state: bool) -> None:
    return generate_scene_image_local(job_id, scene_id, force=force, manage_job_state=manage_job_state)
