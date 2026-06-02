import mimetypes
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlmodel import select

from app.models import Asset, Project, Scene
from app.settings import settings
from app.time_utils import now_utc


async def persist_upload_file(*, file: UploadFile, folder: Path, filename_prefix: str) -> tuple[Path, str, str]:
    folder.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or filename_prefix).suffix.lower()
    ts = now_utc().strftime("%Y%m%d_%H%M%S")
    target = folder / f"{filename_prefix}_{ts}{suffix}"
    content = await file.read()
    target.write_bytes(content)
    rel = str(target.resolve().relative_to(settings.assets_dir)).replace("\\", "/")
    mime = file.content_type or mimetypes.guess_type(str(target))[0] or ""
    return target, rel, mime


def get_project_or_404(session, project_id: int) -> Project:
    project = session.exec(select(Project).where(Project.id == project_id)).first()
    if not project or project.id is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


def get_scene_or_404(session, scene_id: int) -> Scene:
    scene = session.exec(select(Scene).where(Scene.id == scene_id)).first()
    if not scene or scene.id is None:
        raise HTTPException(status_code=404, detail="镜头不存在")
    return scene


def create_asset_in_session(
    session,
    *,
    kind: str,
    rel_path: str,
    mime: str,
    project_id: int,
    tag: str,
    scene_id: int | None = None,
    meta_json: str = "{}",
) -> Asset:
    asset = Asset(
        kind=kind,
        rel_path=rel_path,
        mime=mime,
        project_id=int(project_id),
        scene_id=(int(scene_id) if scene_id is not None else None),
        tag=tag,
        meta_json=meta_json,
    )
    session.add(asset)
    session.flush()
    session.refresh(asset)
    return asset
