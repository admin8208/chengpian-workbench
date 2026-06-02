from typing import Any, cast

import json
import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlalchemy import desc
from sqlmodel import select

from app.access_control import require_project_access
from app.db import session_scope
from app.models import Asset, Project
from app.modules.media.library_import import ImportRequest, import_to_project
from app.presenters import asset_to_out
from app.schemas import AssetOut, LibraryImportIn
from app.settings import settings
from app.time_utils import now_utc, utc_iso_z

router = APIRouter(tags=["asset"])


@router.get("/api/projects/{project_id}/assets", response_model=list[AssetOut])
def get_project_assets(project_id: int, limit: int = 200):
    limit = max(1, min(1000, int(limit)))
    with session_scope() as session:
        require_project_access(session, int(project_id))
        items = session.exec(
            select(Asset).where(Asset.project_id == project_id).order_by(desc(cast(Any, Asset.created_at))).limit(limit)
        ).all()
        return [asset_to_out(asset) for asset in items if asset.id is not None]


@router.post("/api/projects/{project_id}/import-web", response_model=AssetOut)
def import_project_asset(project_id: int, body: LibraryImportIn):
    with session_scope() as session:
        require_project_access(session, int(project_id))
    try:
        asset = import_to_project(
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
            ),
            project_id=int(project_id),
        )
        return asset_to_out(asset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"导入失败：{exc}")


@router.post("/api/projects/{project_id}/assets", response_model=AssetOut)
async def upload_project_asset(project_id: int, file: UploadFile = File(...), kind: str = Form("audio"), tag: str = Form("project_source")):
    kind = (kind or "audio").strip().lower()
    if kind not in ("image", "audio", "video", "other"):
        raise HTTPException(status_code=400, detail="不支持的素材类型")
    with session_scope() as session:
        require_project_access(session, int(project_id))

    suffix = Path(file.filename or "upload").suffix.lower()
    if kind == "audio" and suffix not in (".mp3", ".wav", ".m4a", ".aac"):
        raise HTTPException(status_code=400, detail="音频仅支持 mp3/wav/m4a/aac")
    if kind == "image" and suffix not in (".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(status_code=400, detail="图片仅支持 png/jpg/webp")
    if kind == "video" and suffix not in (".mp4", ".mov", ".mkv", ".webm"):
        raise HTTPException(status_code=400, detail="视频仅支持 mp4/mov/mkv/webm")

    from app.project_paths import project_imported_dir, rel_to_projects_root

    folder = project_imported_dir(int(project_id)) / kind
    folder.mkdir(parents=True, exist_ok=True)
    ts = now_utc().strftime("%Y%m%d_%H%M%S_%f")
    target = folder / f"{kind}_{ts}_{uuid.uuid4().hex[:12]}{suffix or ''}"
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="上传文件为空")
    target.write_bytes(raw)
    rel = rel_to_projects_root(target)
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
    try:
        with session_scope() as session:
            require_project_access(session, int(project_id))
            asset = Asset(kind=kind, rel_path=rel, mime=mime, project_id=int(project_id), scene_id=None, tag=(tag or "project_source").strip() or "project_source", meta_json=json.dumps(meta, ensure_ascii=True))
            session.add(asset)
            session.flush()
            session.refresh(asset)
            return asset_to_out(asset)
    except Exception:
        try:
            target.unlink(missing_ok=True)
        except Exception:
            pass
        raise
