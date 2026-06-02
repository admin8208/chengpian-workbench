from fastapi import APIRouter

from app.application.project_ops import get_final_export_api, start_render_api
from app.modules.ai_project.project_ops import start_ai_images_api, start_ai_scene_image_api
from app.modules.network_project.project_ops import start_network_autofill_media_api
from app.schemas import JobCreateOut

router = APIRouter(tags=["project-ops"])


@router.post("/api/projects/{project_id}/render", response_model=JobCreateOut)
def start_render(project_id: int):
    return start_render_api(project_id)


@router.get("/api/projects/{project_id}/exports/final", response_model=dict)
def get_final_export(project_id: int):
    return get_final_export_api(project_id)


@router.post("/api/projects/{project_id}/images", response_model=JobCreateOut)
def start_images(project_id: int):
    return start_ai_images_api(project_id)


@router.post("/api/projects/{project_id}/autofill-media", response_model=JobCreateOut)
def start_autofill_media(project_id: int, prefer: str = "video"):
    return start_network_autofill_media_api(project_id, prefer)


@router.post("/api/scenes/{scene_id}/generate-image", response_model=JobCreateOut)
def start_scene_image(scene_id: int):
    return start_ai_scene_image_api(scene_id)
