from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import desc
from sqlmodel import Session, select

from app.access_control import require_project_access
from app.api_common import ensure_project_storage_clean, project_storage_leftovers
from app.db import session_scope
from app.job_control import finalize_cancelled_job_if_stale_in_session
from app.jobs import request_job_cancel
from app.models import Asset, Job, Project, Scene, Variant
from app.projection_store import delete_job_projections, delete_project_projection
from app.project_paths import projects_root_dir
from app.schemas import OkOut
from app.settings import settings
from app.time_utils import now_utc


def _collect_project_asset_ids(project: Project, scenes: list[Scene]) -> set[int]:
    asset_ids: set[int] = set()
    for maybe_id in (getattr(project, "role_image_asset_id", None), getattr(project, "voice_asset_id", None), getattr(project, "subtitle_asset_id", None)):
        try:
            if maybe_id is not None and int(maybe_id) > 0:
                asset_ids.add(int(maybe_id))
        except Exception:
            continue
    for scene in scenes:
        try:
            if getattr(scene, "image_asset_id", None) is not None and int(scene.image_asset_id) > 0:
                asset_ids.add(int(scene.image_asset_id))
        except Exception:
            continue
    return asset_ids


def _project_deletion_db_leftovers(session: Session, project_id: int) -> list[str]:
    leftovers: list[str] = []
    pid = int(project_id)
    if session.exec(select(Project).where(Project.id == pid)).first():
        leftovers.append(f"Project:{pid}")
    if session.exec(select(Scene).where(Scene.project_id == pid)).first():
        leftovers.append(f"Scene:project_id={pid}")
    if session.exec(select(Job).where(Job.project_id == pid)).first():
        leftovers.append(f"Job:project_id={pid}")
    if session.exec(select(Asset).where(Asset.project_id == pid)).first():
        leftovers.append(f"Asset:project_id={pid}")
    if session.exec(select(Variant).where(Variant.project_id == pid)).first():
        leftovers.append(f"Variant:project_id={pid}")
    return leftovers


def _asset_storage_root(asset: Asset) -> Path:
    rel = str(asset.rel_path or "").strip().lstrip("/")
    if rel.startswith("project_"):
        return projects_root_dir()
    tag = str(asset.tag or "").strip().lower()
    if str(asset.kind or "") == "video" and tag in ("export", "export_history"):
        return settings.exports_dir
    return settings.assets_dir


def delete_project_api(project_id: int) -> OkOut:
    asset_file_refs: set[tuple[Path, str]] = set()

    with session_scope() as session:
        project = require_project_access(session, project_id)

        pending_cancel_jobs = session.exec(
            select(Job)
            .where(Job.project_id == int(project_id))
            .where(Job.status.in_(["queued", "running", "paused"]))
            .where(Job.cancel_requested == True)
            .order_by(desc(Job.created_at))
        ).all()
        for job in pending_cancel_jobs:
            if getattr(job, "id", None) is not None:
                finalize_cancelled_job_if_stale_in_session(session, int(job.id))

        active_jobs = session.exec(
            select(Job)
            .where(Job.project_id == int(project_id))
            .where(Job.status.in_(["queued", "running", "paused"]))
            .order_by(desc(Job.created_at))
        ).all()
        if active_jobs:
            running_jobs = [job for job in active_jobs if str(job.status or "") == "running"]
            if running_jobs:
                latest = running_jobs[0]
                request_job_cancel(int(latest.id), source="delete_project", reason="项目删除")
                raise HTTPException(status_code=409, detail=f"项目仍有任务正在停止：{latest.kind} · {latest.status}，请稍后重试删除")
            for job in active_jobs:
                status = str(job.status or "").strip().lower()
                if status == "queued":
                    job.status = "cancelled"
                    job.progress = 100
                    job.message = "项目删除：任务已取消"
                    job.cancel_source = "delete_project"
                    job.cancel_reason = "项目删除"
                    job.updated_at = now_utc()
                    session.add(job)
                    continue
                request_job_cancel(int(job.id), source="delete_project", reason="项目删除")
                raise HTTPException(status_code=409, detail=f"项目仍有任务正在停止：{job.kind} · {job.status}，请稍后重试删除")

        scenes = session.exec(select(Scene).where(Scene.project_id == int(project_id))).all()
        asset_ids = _collect_project_asset_ids(project, scenes)
        assets = session.exec(select(Asset).where(Asset.project_id == int(project_id))).all()
        if asset_ids:
            bound_assets = session.exec(select(Asset).where(Asset.id.in_(sorted(asset_ids)))).all()
            assets_by_id = {int(asset.id): asset for asset in assets if getattr(asset, "id", None) is not None}
            for asset in bound_assets:
                if asset and getattr(asset, "id", None) is not None:
                    assets_by_id[int(asset.id)] = asset
            assets = list(assets_by_id.values())

        for asset in assets:
            rel = str(getattr(asset, "rel_path", "") or "").strip()
            if rel:
                asset_file_refs.add((_asset_storage_root(asset).resolve(), rel))

    leftovers = ensure_project_storage_clean(project_id, extra_file_refs=sorted(asset_file_refs, key=lambda item: (str(item[0]), item[1])))
    if leftovers:
        sample = "；".join(str(item) for item in leftovers[:3])
        raise HTTPException(status_code=500, detail=f"删除项目文件失败，仍有残留内容未清理：{sample}")

    with session_scope() as session:
        try:
            project = require_project_access(session, project_id)
        except HTTPException as exc:
            if exc.status_code == 404:
                return OkOut(ok=True)
            raise
        scenes = session.exec(select(Scene).where(Scene.project_id == int(project_id))).all()
        jobs = session.exec(select(Job).where(Job.project_id == int(project_id))).all()
        variants = session.exec(select(Variant).where(Variant.project_id == int(project_id))).all()
        assets = session.exec(select(Asset).where(Asset.project_id == int(project_id))).all()
        for scene in scenes:
            session.delete(scene)
        for variant in variants:
            session.delete(variant)
        for job in jobs:
            session.delete(job)
        for asset in assets:
            session.delete(asset)
        session.delete(project)

        db_leftovers = _project_deletion_db_leftovers(session, project_id)
        if db_leftovers:
            sample = "；".join(db_leftovers[:5])
            raise HTTPException(status_code=500, detail=f"项目磁盘文件已清理，但数据库仍有残留记录：{sample}")

    verify_leftovers = project_storage_leftovers(project_id)
    if verify_leftovers:
        sample = "；".join(verify_leftovers[:3])
        raise HTTPException(status_code=500, detail=f"项目记录已删除，但磁盘上仍有残留目录：{sample}")

    delete_project_projection(int(project_id))
    delete_job_projections(int(project_id))

    return OkOut(ok=True)
