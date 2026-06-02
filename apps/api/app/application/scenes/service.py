import json
import shutil
from pathlib import Path

from fastapi import HTTPException
from sqlmodel import select

from app.access_control import require_asset_access, require_scene_access
from app.db import session_scope
from app.material_policies import asset_material_mode, asset_mode_label, material_mode_label, project_material_mode
from app.models import Asset, Project, Scene
from app.presenters import asset_to_out, scene_to_out
from app.project_paths import asset_disk_path, project_imported_dir, rel_to_projects_root
from app.schemas import AssetOut, SceneBindAssetIn, SceneOut, ScenePatchIn
from app.storyboard_postprocess import canonical_script_from_scenes
from app.time_utils import now_utc


def _mark_scene_asset_bound(scene: Scene, *, media_pipeline: str = "manual_asset", project_mode: str = "network", asset_mode: str = "network") -> None:
    meta = {}
    try:
        meta = json.loads(getattr(scene, "meta_json", "{}") or "{}")
        if not isinstance(meta, dict):
            meta = {}
    except Exception:
        meta = {}
    meta["media_pipeline"] = str(media_pipeline or "manual_asset")
    meta.setdefault("search", {})
    if isinstance(meta.get("search"), dict):
        meta["search"].pop("needs_review", None)
        meta["search"].pop("confirmed_at", None)
        meta["search"].pop("llm_reason", None)
    meta["binding_material_mode"] = str(project_mode or "network")
    meta["project_material_mode"] = str(project_mode or "network")
    meta["bound_asset_material_mode"] = str(asset_mode or "network")
    meta.pop("cross_mode_override", None)
    meta.pop("cross_mode_confirmed_at", None)
    meta.pop("cross_mode_asset_id", None)
    scene.meta_json = json.dumps(meta, ensure_ascii=True)


def _assert_asset_mode_compatible(*, project_mode: str, asset: Asset) -> tuple[str, str]:
    asset_mode = asset_material_mode(asset)
    if project_mode != asset_mode:
        raise HTTPException(
            status_code=409,
            detail=f"当前项目是{material_mode_label(project_mode)}，不能直接绑定{asset_mode_label(asset_mode)}。请使用与当前模式一致的镜头素材。",
        )
    return project_mode, asset_mode


def _project_private_asset(session, *, project_id: int, scene_id: int | None, asset: Asset) -> Asset:
    if int(asset.project_id or 0) == int(project_id):
        return asset
    rel = str(asset.rel_path or "").strip()
    if not rel:
        raise HTTPException(status_code=400, detail="素材文件不存在")
    src = asset_disk_path(rel, is_export=bool(str(asset.kind or "") == "video" and str(asset.tag or "") in ("export", "export_history")))
    if not src.exists() or not src.is_file():
        if int(asset.project_id or 0) == 0 and str(asset.tag or "").strip().lower() == "library":
            raise HTTPException(status_code=409, detail="公共素材库中的该素材文件已丢失，请先在素材库中删除这条失效记录并重新导入素材")
        raise HTTPException(status_code=400, detail="素材文件不存在")
    folder = project_imported_dir(project_id) / str(asset.kind or "other")
    folder.mkdir(parents=True, exist_ok=True)
    ts = now_utc().strftime("%Y%m%d_%H%M%S_%f")
    suffix = Path(src.name).suffix or ""
    dst = folder / f"asset_{int(asset.id or 0)}_{ts}{suffix}"
    shutil.copyfile(src, dst)
    try:
        meta = json.loads(getattr(asset, "meta_json", "{}") or "{}")
        if not isinstance(meta, dict):
            meta = {}
    except Exception:
        meta = {}
    meta["copied_from_asset_id"] = int(asset.id or 0)
    meta["copied_into_project_id"] = int(project_id)
    dup = Asset(
        kind=str(asset.kind or "image"),
        rel_path=rel_to_projects_root(dst),
        mime=str(asset.mime or ""),
        project_id=int(project_id),
        scene_id=(int(scene_id) if scene_id is not None else None),
        tag="project_asset",
        meta_json=json.dumps(meta, ensure_ascii=True),
    )
    session.add(dup)
    session.flush()
    session.refresh(dup)
    return dup


def patch_scene_api(scene_id: int, body: ScenePatchIn) -> SceneOut:
    with session_scope() as session:
        s = require_scene_access(session, scene_id)
        project_id = int(s.project_id)
        if body.narration is not None:
            s.narration = body.narration
        if getattr(body, "media_query", None) is not None:
            s.media_query = (body.media_query or "").strip()
        if body.image_prompt is not None:
            s.image_prompt = body.image_prompt
        if body.image_negative is not None:
            s.image_negative = body.image_negative
        if body.duration_sec is not None:
            s.duration_sec = float(body.duration_sec)
        if getattr(body, "meta", None) is not None:
            cur = {}
            try:
                cur = json.loads(getattr(s, "meta_json", "{}") or "{}")
                if not isinstance(cur, dict):
                    cur = {}
            except Exception:
                cur = {}
            patch = body.meta or {}
            if not isinstance(patch, dict):
                patch = {}
            try:
                cur.update(patch)
            except Exception:
                pass
            s.meta_json = json.dumps(cur, ensure_ascii=True)
        s.updated_at = now_utc()
        session.add(s)
        session.flush()
        if body.narration is not None:
            rows = session.exec(select(Scene).where(Scene.project_id == project_id).order_by(Scene.idx)).all()
            canonical_script = canonical_script_from_scenes([{"idx": int(getattr(row, "idx", 0) or 0), "narration": str(getattr(row, "narration", "") or "")} for row in rows])
            p = session.exec(select(Project).where(Project.id == project_id)).first()
            if p and canonical_script:
                p.script = canonical_script
                p.updated_at = now_utc()
                session.add(p)
            session.flush()
        session.refresh(s)
        return scene_to_out(session, s)


def bind_scene_asset_api(scene_id: int, body: SceneBindAssetIn) -> SceneOut:
    with session_scope() as session:
        s = require_scene_access(session, scene_id)
        a = require_asset_access(session, int(body.asset_id))
        if str(a.kind) not in ("image", "video"):
            raise HTTPException(status_code=400, detail="仅支持绑定图片/视频素材")
        if int(a.project_id or 0) not in (0, int(s.project_id)):
            raise HTTPException(status_code=400, detail="素材不属于当前项目")
        project = session.exec(select(Project).where(Project.id == int(s.project_id))).first()
        project_mode = project_material_mode(project)
        project_mode, bound_asset_mode = _assert_asset_mode_compatible(project_mode=project_mode, asset=a)
        a = _project_private_asset(session, project_id=int(s.project_id), scene_id=int(s.id), asset=a)
        s.image_asset_id = int(a.id)
        s.status = "ready"
        _mark_scene_asset_bound(s, media_pipeline="manual_asset", project_mode=project_mode, asset_mode=bound_asset_mode)
        s.updated_at = now_utc()
        session.add(s)
        session.flush()
        session.refresh(s)
        return scene_to_out(session, s)


def list_scene_image_assets_api(scene_id: int, limit: int = 100) -> list[AssetOut]:
    limit = max(1, min(500, int(limit)))
    with session_scope() as session:
        require_scene_access(session, scene_id)
        items = session.exec(select(Asset).where(Asset.scene_id == scene_id).where(Asset.kind.in_(["image", "video"])).order_by(Asset.created_at.desc()).limit(limit)).all()
        return [asset_to_out(a) for a in items if a.id is not None]


def use_scene_image_api(scene_id: int, asset_id: int) -> SceneOut:
    with session_scope() as session:
        s = require_scene_access(session, scene_id)
        a = require_asset_access(session, asset_id)
        if a.kind not in ("image", "video"):
            raise HTTPException(status_code=400, detail="该素材不是图片/视频")
        if a.scene_id and int(a.scene_id) != int(scene_id):
            raise HTTPException(status_code=400, detail="该素材不属于当前镜头")
        if a.project_id and int(a.project_id) != int(s.project_id):
            raise HTTPException(status_code=400, detail="该素材不属于当前项目")
        project = session.exec(select(Project).where(Project.id == int(s.project_id))).first()
        project_mode = project_material_mode(project)
        project_mode, bound_asset_mode = _assert_asset_mode_compatible(project_mode=project_mode, asset=a)
        a = _project_private_asset(session, project_id=int(s.project_id), scene_id=int(s.id), asset=a)
        s.image_asset_id = int(a.id)
        s.status = "ready"
        _mark_scene_asset_bound(s, media_pipeline="manual_asset", project_mode=project_mode, asset_mode=bound_asset_mode)
        s.updated_at = now_utc()
        session.add(s)
        session.flush()
        session.refresh(s)
        return scene_to_out(session, s)
