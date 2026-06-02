import json
import mimetypes
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlalchemy import desc
from sqlmodel import select

from app.api_common import safe_unlink
from app.db import session_scope
from app.models import Asset
from app.modules.media.library_import import ImportRequest, import_to_library
from app.presenters import asset_to_out
from app.schemas import AssetOut, LibraryImportIn
from app.settings import settings
from app.time_utils import now_utc, utc_iso_z

from .asset_guard import library_asset_delete_block_reason

router = APIRouter(tags=["asset"])


@router.get("/api/library/assets", response_model=list[AssetOut])
def get_library_assets(kind: str = "image", query: str = "", limit: int = 60):
    kind = (kind or "image").strip().lower()
    if kind not in ("image", "audio", "video", "other"):
        kind = "image"
    limit = max(1, min(500, int(limit or 60)))
    q = (query or "").strip().lower()
    with session_scope() as session:
        items = session.exec(
            select(Asset).where(Asset.tag == "library").where(Asset.kind == kind).order_by(desc(cast(Any, Asset.created_at))).limit(limit)
        ).all()
        out: list[AssetOut] = []
        for asset in items:
            if asset.id is None:
                continue
            if q:
                hay = " ".join([str(asset.rel_path or ""), str(asset.tag or ""), str(getattr(asset, "meta_json", "") or "")]).lower()
                if q not in hay:
                    continue
            out.append(asset_to_out(asset))
        return out


@router.post("/api/library/import", response_model=AssetOut)
def import_asset(body: LibraryImportIn):
    try:
        asset = import_to_library(
            ImportRequest(
                provider=body.provider,
                kind=body.kind,
                title=body.title,
                page_url=body.page_url,
                file_url=body.file_url,
                width=body.width,
                height=body.height,
                duration_sec=body.duration_sec,
                thumb_url=body.thumb_url,
                preview_url=body.preview_url,
                license_short=body.license_short,
                license_url=body.license_url,
                author=body.author,
                attribution=body.attribution,
            )
        )
        return asset_to_out(asset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"导入失败：{exc}")


@router.post("/api/library/assets", response_model=AssetOut)
async def upload_library_asset(file: UploadFile = File(...), kind: str = Form("image"), tag: str = Form("library")):
    kind = (kind or "image").strip().lower()
    if kind not in ("image", "audio", "video", "other"):
        kind = "image"
    tag = (tag or "library").strip() or "library"

    suffix = Path(file.filename or "upload").suffix.lower()
    if kind == "image" and suffix not in (".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(status_code=400, detail="图片仅支持 png/jpg/webp")
    if kind == "audio" and suffix not in (".mp3", ".wav", ".m4a", ".aac"):
        raise HTTPException(status_code=400, detail="音频仅支持 mp3/wav/m4a/aac")
    if kind == "video" and suffix not in (".mp4", ".mov", ".mkv", ".webm"):
        raise HTTPException(status_code=400, detail="视频仅支持 mp4/mov/mkv/webm")

    folder = settings.assets_dir / "library" / kind
    folder.mkdir(parents=True, exist_ok=True)
    ts = now_utc().strftime("%Y%m%d_%H%M%S")
    target = folder / f"{kind}_{ts}{suffix or ''}"
    target.write_bytes(await file.read())

    rel = str(target.resolve().relative_to(settings.assets_dir)).replace("\\", "/")
    mime = file.content_type or mimetypes.guess_type(str(target))[0] or ""
    original_name = Path(file.filename or target.name).name
    title = Path(original_name).stem or f"{kind}_{ts}"
    meta = {
        "provider": "local_upload",
        "kind": kind,
        "title": title[:120],
        "original_filename": original_name,
        "uploaded_at": utc_iso_z(),
    }
    with session_scope() as session:
        asset = Asset(
            kind=kind,
            rel_path=rel,
            mime=mime,
            project_id=None,
            scene_id=None,
            tag=tag,
            meta_json=json.dumps(meta, ensure_ascii=True),
        )
        session.add(asset)
        session.flush()
        session.refresh(asset)
        return asset_to_out(asset)


@router.delete("/api/library/assets/{asset_id}")
def delete_library_asset(asset_id: int):
    with session_scope() as session:
        asset = session.exec(select(Asset).where(Asset.id == asset_id)).first()
        if not asset or asset.id is None or str(asset.tag or "") != "library":
            raise HTTPException(status_code=404, detail="素材不存在")
        blocked = library_asset_delete_block_reason(session, int(asset.id))
        if blocked:
            raise HTTPException(status_code=409, detail=blocked)
        rel = str(asset.rel_path or "").strip()
        session.delete(asset)
    if rel:
        safe_unlink(settings.assets_dir, rel)
    return {"ok": True, "deleted": 1}


@router.delete("/api/library/assets")
def clear_library_assets(kind: str = "video"):
    kind = (kind or "video").strip().lower()
    if kind not in ("image", "audio", "video", "other"):
        kind = "video"
    deleted = 0
    skipped_active = 0
    rel_paths: list[str] = []
    with session_scope() as session:
        assets = session.exec(
            select(Asset)
            .where(Asset.tag == "library")
            .where(Asset.kind == kind)
            .order_by(desc(cast(Any, Asset.created_at)))
        ).all()
        for asset in assets:
            if asset.id is None:
                continue
            blocked = library_asset_delete_block_reason(session, int(asset.id))
            if blocked:
                skipped_active += 1
                continue
            rel = str(asset.rel_path or "").strip()
            if rel:
                rel_paths.append(rel)
            session.delete(asset)
            deleted += 1
    for rel in rel_paths:
        safe_unlink(settings.assets_dir, rel)
    return {"ok": True, "deleted": deleted, "skipped_active": skipped_active}
