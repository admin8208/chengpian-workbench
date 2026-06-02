import json
from pathlib import Path

from sqlmodel import select

from app.models import Asset, Scene
from app.time_utils import now_utc


def save_generated_scene_image(
    *,
    pid: int,
    scene_idx: int,
    image_bytes: bytes,
    mime: str,
    meta: dict,
    project_generated_dir,
    rel_to_projects_root,
    guess_image_ext,
):
    ts = now_utc().strftime("%Y%m%d_%H%M%S")
    ext = guess_image_ext(mime, meta)
    out_path = project_generated_dir(pid) / f"scene_{scene_idx:03d}_{ts}{ext}"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(image_bytes)
    return out_path


def bind_generated_scene_asset(
    *,
    session_scope,
    scene_id: int,
    pid: int,
    out_path: Path,
    mime: str,
    meta: dict,
    rel_to_projects_root,
) -> None:
    with session_scope() as session:
        asset = Asset(
            kind="image",
            rel_path=rel_to_projects_root(out_path),
            mime=mime,
            project_id=pid,
            scene_id=int(scene_id),
            tag="scene_generated_ai",
            meta_json=json.dumps(meta, ensure_ascii=True),
        )
        session.add(asset)
        session.flush()
        session.refresh(asset)

        scene = session.exec(select(Scene).where(Scene.id == scene_id)).first()
        if scene:
            existing_meta = json.loads(scene.meta_json or "{}") if str(scene.meta_json or "").strip() else {}
            if not isinstance(existing_meta, dict):
                existing_meta = {}
            scene.image_asset_id = asset.id
            scene.status = "ready"
            scene.meta_json = json.dumps(
                {
                    **existing_meta,
                    "material_mode": "ai",
                    "media_pipeline": "ai_image",
                    "generated_by": "image_provider",
                    "generated_asset_id": int(asset.id or 0),
                    "last_image_generation_failed": False,
                    "last_image_generation_error": "",
                    "preserved_previous_image": False,
                },
                ensure_ascii=True,
            )
            scene.updated_at = now_utc()
            session.add(scene)


def mark_scene_generate_failed(*, session_scope, scene_id: int, error_message: str = "", preserve_existing_asset: bool = True) -> None:
    with session_scope() as session:
        scene = session.exec(select(Scene).where(Scene.id == scene_id)).first()
        if scene:
            existing_meta = json.loads(scene.meta_json or "{}") if str(scene.meta_json or "").strip() else {}
            if not isinstance(existing_meta, dict):
                existing_meta = {}
            has_existing_asset = bool(getattr(scene, "image_asset_id", None))
            scene.status = "ready" if preserve_existing_asset and has_existing_asset else "failed"
            scene.meta_json = json.dumps(
                {
                    **existing_meta,
                    "last_image_generation_failed": True,
                    "last_image_generation_error": str(error_message or "").strip(),
                    "preserved_previous_image": bool(preserve_existing_asset and has_existing_asset),
                },
                ensure_ascii=True,
            )
            scene.updated_at = now_utc()
            session.add(scene)
