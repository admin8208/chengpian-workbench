from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import select

from app.access_control import require_project_access
from app.db import session_scope
from app.job_dispatcher import enqueue_project_job
from app.material_policies import material_mode_label, project_material_mode
from app.models import Project
from app.schemas import JobCreateOut


def _autofill_media(job_id: int, project_id: int, *, prefer: str):
    from app.tasks_entries import autofill_media

    return autofill_media.schedule(args=(job_id, project_id), kwargs={"prefer": prefer}, delay=0)


def _require_project_material_mode(project_id: int, expected_mode: str, *, action_label: str) -> Project:
    with session_scope() as session:
        project = require_project_access(session, int(project_id))
        actual_mode = project_material_mode(project)
        if actual_mode != expected_mode:
            raise HTTPException(status_code=409, detail=f"当前项目是{material_mode_label(actual_mode)}，不能执行{action_label}。请切换模式或改用对应操作。")
        return project


def start_network_autofill_media_api(project_id: int, prefer: str = "video") -> JobCreateOut:
    _require_project_material_mode(project_id, "network", action_label="自动补素材")
    prefer = (prefer or "video").strip().lower()
    if prefer not in ("video", "image"):
        prefer = "video"
    job = enqueue_project_job(
        kind="autofill_media",
        project_id=project_id,
        message="排队中",
        payload={"project_id": project_id, "prefer": prefer},
        enqueue=lambda job_id: _autofill_media(job_id, project_id, prefer=prefer),
        enqueue_error_message="自动补素材任务入队失败，请检查后台任务服务",
    )
    return JobCreateOut(job=job)
