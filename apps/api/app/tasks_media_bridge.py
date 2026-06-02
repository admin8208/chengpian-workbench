from pathlib import Path

from sqlmodel import select

from app.models import Asset, Project
from app.project_paths import asset_disk_path
from app.tasks_media_entry_impl import autofill_media_local as autofill_media_entry_local


def get_role_asset_path_bridge(session, project: Project) -> Path | None:
    if not project.role_image_asset_id:
        return None
    asset = session.exec(select(Asset).where(Asset.id == project.role_image_asset_id)).first()
    if not asset:
        return None
    path = asset_disk_path(str(asset.rel_path or ""), is_export=False)
    return path if path.exists() else None


def autofill_media_local_bridge(
    job_id: int,
    project_id: int,
    prefer: str = "video",
    *,
    outer_job_id: int | None = None,
    progress_base: int = 0,
    progress_span: int = 100,
    keep_running: bool = False,
    media_impl=None,
) -> None:
    if media_impl is None:
        from app.tasks_media_facade import autofill_media_impl_local as media_impl_local

        media_impl = media_impl_local
    autofill_media_entry_local(
        job_id,
        project_id,
        prefer=prefer,
        outer_job_id=outer_job_id,
        progress_base=progress_base,
        progress_span=progress_span,
        keep_running=keep_running,
        media_impl=media_impl,
    )
