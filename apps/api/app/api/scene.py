from fastapi import APIRouter

from app.modules.ai_project.scene_service import list_ai_scene_image_assets_api, patch_ai_scene_api, use_ai_scene_image_api
from app.modules.network_project.scene_service import bind_network_scene_asset_api, list_network_scene_image_assets_api, patch_network_scene_api
from app.schemas import AssetOut, SceneBindAssetIn, SceneOut, ScenePatchIn

router = APIRouter(tags=["scene"])


@router.patch("/api/scenes/{scene_id}", response_model=SceneOut)
def patch_scene(scene_id: int, body: ScenePatchIn):
    if body.image_prompt is not None or body.image_negative is not None:
        return patch_ai_scene_api(scene_id, body)
    return patch_network_scene_api(scene_id, body)


@router.post("/api/scenes/{scene_id}/bind-asset", response_model=SceneOut)
def bind_scene_asset(scene_id: int, body: SceneBindAssetIn):
    return bind_network_scene_asset_api(scene_id, body)


@router.get("/api/scenes/{scene_id}/image-assets", response_model=list[AssetOut])
def list_scene_image_assets(scene_id: int, limit: int = 100):
    return list_network_scene_image_assets_api(scene_id, limit)


@router.post("/api/scenes/{scene_id}/use-image/{asset_id}", response_model=SceneOut)
def use_scene_image(scene_id: int, asset_id: int):
    return use_ai_scene_image_api(scene_id, asset_id)
