from fastapi import HTTPException
from sqlmodel import select

from app.access_control import require_project_access, require_scene_access
from app.api_common import check_render_quality, stable_final_export_status
from app.db import session_scope
from app.job_dispatcher import enqueue_project_job
from app.material_policies import material_mode_label, project_material_mode
from app.models import Project, Scene
from app.schemas import JobCreateOut, RenderBatchIn, RenderBatchOut


def _generate_project_images(job_id: int, project_id: int, *, force: bool = True):
    from app.tasks_entries import generate_project_images

    return generate_project_images.schedule(args=(job_id, project_id), kwargs={"force": force}, delay=0)


def _generate_scene_image(job_id: int, scene_id: int, *, force: bool = True):
    from app.tasks_entries import generate_scene_image

    return generate_scene_image.schedule(args=(job_id, scene_id), kwargs={"force": force}, delay=0)


def _render_guard(project_id: int) -> None:
    quality_check = check_render_quality(project_id)
    if not quality_check.get("ready"):
        raise HTTPException(status_code=400, detail={"message": "质量检查未通过", "quality_check": quality_check})


def _render_video(job_id: int, project_id: int):
    from app.tasks_entries import render_video

    return render_video.schedule(args=(job_id, project_id), delay=0)


def _autofill_media(job_id: int, project_id: int, *, prefer: str):
    from app.tasks_entries import autofill_media

    return autofill_media.schedule(args=(job_id, project_id), kwargs={"prefer": prefer}, delay=0)


def _require_project_material_mode(project_id: int, expected_mode: str, *, action_label: str) -> Project:
    with session_scope() as session:
        project = require_project_access(session, int(project_id))
        actual_mode = project_material_mode(project)
        if actual_mode != expected_mode:
            raise HTTPException(
                status_code=409,
                detail=f"当前项目是{material_mode_label(actual_mode)}，不能执行{action_label}。请切换模式或改用对应操作。",
            )
        return project


def start_render_api(project_id: int) -> JobCreateOut:
    with session_scope() as session:
        require_project_access(session, int(project_id))
    _render_guard(project_id)
    job = enqueue_project_job(
        kind="render",
        project_id=project_id,
        message="排队中",
        payload={"project_id": project_id, "render_substage": "tts_prepare"},
        enqueue=lambda job_id: _render_video(job_id, project_id),
        enqueue_error_message="渲染任务入队失败，请检查后台任务服务",
    )
    return JobCreateOut(job=job)


def start_render_batch_api(project_id: int, body: RenderBatchIn) -> RenderBatchOut:
    with session_scope() as session:
        require_project_access(session, int(project_id))
    _render_guard(project_id)
    job = enqueue_project_job(
        kind="render",
        project_id=project_id,
        message="排队中",
        payload={"project_id": project_id, "single_output": True, "render_substage": "tts_prepare"},
        enqueue=lambda job_id: _render_video(job_id, project_id),
        enqueue_error_message="批量渲染任务入队失败，请检查后台任务服务",
    )
    return RenderBatchOut(jobs=[job])


def get_final_export_api(project_id: int) -> dict:
    with session_scope() as session:
        require_project_access(session, int(project_id))
    return stable_final_export_status(project_id)


def start_images_api(project_id: int) -> JobCreateOut:
    _require_project_material_mode(project_id, "ai", action_label="智能生图")
    job = enqueue_project_job(
        kind="images",
        project_id=project_id,
        message="排队中",
        payload={"project_id": project_id, "force": True},
        enqueue=lambda job_id: _generate_project_images(job_id, project_id, force=True),
        enqueue_error_message="智能生图任务入队失败，请检查后台任务服务",
    )
    return JobCreateOut(job=job)


def start_autofill_media_api(project_id: int, prefer: str = "video") -> JobCreateOut:
    _require_project_material_mode(project_id, "network", action_label="自动补素材")
    prefer = (prefer or "video").strip().lower()
    if prefer not in ("video", "image"):
        prefer = "video"
    job = enqueue_project_job(
        kind="autofill_media",
        project_id=project_id,
        message="排队中",
        payload={"project_id": project_id, "prefer": prefer},
        enqueue=lambda job_id: _autofill_media(job_id, project_id, prefer=prefer),
        enqueue_error_message="自动补素材任务入队失败，请检查后台任务服务",
    )
    return JobCreateOut(job=job)


def start_scene_image_api(scene_id: int) -> JobCreateOut:
    with session_scope() as session:
        scene = require_scene_access(session, int(scene_id))
        project_id = int(scene.project_id)
    _require_project_material_mode(project_id, "ai", action_label="单镜头智能生图")
    job = enqueue_project_job(
        kind="scene_image",
        project_id=project_id,
        message="排队中",
        payload={"project_id": project_id, "scene_id": int(scene_id), "force": True},
        enqueue=lambda job_id: _generate_scene_image(job_id, int(scene_id), force=True),
        enqueue_error_message="单镜头生图任务入队失败，请检查后台任务服务",
    )
    return JobCreateOut(job=job)
