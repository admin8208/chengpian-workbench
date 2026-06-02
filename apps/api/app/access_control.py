from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import Asset, Job, Project, Scene


_principal_ctx: ContextVar[dict[str, Any] | None] = ContextVar("chengpian_principal", default=None)


def set_current_principal(principal: dict[str, Any] | None) -> Token:
    return _principal_ctx.set(principal)


def reset_current_principal(token: Token) -> None:
    _principal_ctx.reset(token)


def current_principal() -> dict[str, Any] | None:
    return _principal_ctx.get()


def _is_admin(principal: dict[str, Any] | None) -> bool:
    return bool(principal and principal.get("is_admin"))


def _member_user_id(principal: dict[str, Any] | None) -> int | None:
    if not principal or _is_admin(principal):
        return None
    try:
        value = int(principal.get("user_id"))
    except Exception:
        return None
    return value if value > 0 else None


def can_access_project(project: Project, principal: dict[str, Any] | None = None) -> bool:
    principal = principal if principal is not None else current_principal()
    if principal is None:
        return True
    if _is_admin(principal):
        return True
    user_id = _member_user_id(principal)
    if user_id is None:
        return False
    try:
        return int(getattr(project, "owner_user_id", 0) or 0) == user_id
    except Exception:
        return False


def require_project_access(session: Session, project_id: int) -> Project:
    project = session.exec(select(Project).where(Project.id == int(project_id))).first()
    if not project or project.id is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not can_access_project(project):
        raise HTTPException(status_code=403, detail="无权访问该项目")
    return project


def visible_project_query(query):
    principal = current_principal()
    if principal is None or _is_admin(principal):
        return query
    user_id = _member_user_id(principal)
    if user_id is None:
        return query.where(Project.id == -1)
    return query.where(Project.owner_user_id == user_id)


def visible_project_ids(session: Session, project_ids: list[int] | set[int]) -> set[int]:
    ids = sorted({int(project_id) for project_id in project_ids if int(project_id or 0) > 0})
    if not ids:
        return set()
    query = visible_project_query(select(Project.id).where(Project.id.in_(ids)))
    return {int(project_id) for project_id in session.exec(query).all() if project_id is not None}


def require_scene_access(session: Session, scene_id: int) -> Scene:
    scene = session.exec(select(Scene).where(Scene.id == int(scene_id))).first()
    if not scene or scene.id is None:
        raise HTTPException(status_code=404, detail="镜头不存在")
    require_project_access(session, int(scene.project_id))
    return scene


def require_job_access(session: Session, job_id: int) -> Job:
    job = session.exec(select(Job).where(Job.id == int(job_id))).first()
    if not job or job.id is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    project_id = int(getattr(job, "project_id", 0) or 0)
    if project_id > 0:
        require_project_access(session, project_id)
    elif current_principal() is not None and not _is_admin(current_principal()):
        raise HTTPException(status_code=403, detail="无权访问该系统任务")
    return job


def require_asset_access(session: Session, asset_id: int) -> Asset:
    asset = session.exec(select(Asset).where(Asset.id == int(asset_id))).first()
    if not asset or asset.id is None:
        raise HTTPException(status_code=404, detail="素材不存在")
    project_id = int(getattr(asset, "project_id", 0) or 0)
    if project_id > 0:
        require_project_access(session, project_id)
        return asset
    scene_id = int(getattr(asset, "scene_id", 0) or 0)
    if scene_id > 0:
        require_scene_access(session, scene_id)
    return asset


def owner_fields_for_current_principal() -> dict[str, Any]:
    principal = current_principal()
    if not principal:
        return {}
    return {
        "owner_user_id": _member_user_id(principal),
        "owner_username": str(principal.get("username") or "").strip(),
    }
