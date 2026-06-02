import json
from collections.abc import Callable

from fastapi import HTTPException
from sqlmodel import select

from app.access_control import current_principal, require_job_access, require_project_access, visible_project_ids
from app.api_common import PROTECTED_JOB_KINDS, autopilot_continue_stage, delete_outputs_for_job, job_error_meta, job_out, latest_autopilot_job
from app.db import session_scope
from app.job_dispatcher import enqueue_project_job
from app.jobs import pause_job, request_job_cancel, resume_job
from app.models import Job, Project
from app.modules.pipeline.repository import get_pipeline_run
from app.modules.pipeline.state import pipeline_stage_label
from app.schemas import JobCreateOut, JobOut, OkOut
from app.services.job_presenters import _job_stage_fields
from app.tasks_entries import (
    autopilot_run,
    autofill_media,
    generate_project_images,
    generate_scene_image,
    prepare_project_script,
    render_video,
)
from app.tasks_tts_install import (
    tts_offline_install,
    tts_offline_install_all_compatible,
)


ACTIVE_JOB_STATUSES = {"queued", "running", "paused"}

RetryEnqueue = Callable[[int], object]


def _refresh_projection(project_id: int) -> None:
    if int(project_id or 0) <= 0:
        return
    from app.application.feed import refresh_project_projection

    refresh_project_projection(int(project_id))


def _retry_payload_for_kind(kind: str, payload: dict) -> dict:
    next_payload = {**payload}
    for key in (
        "error_code",
        "blocking_component",
        "recommended_action",
        "recoverable",
        "cancel_requested",
        "cancel_source",
        "cancel_reason",
        "pause_requested",
        "worker_id",
        "worker_pid",
        "worker_started_at",
        "worker_heartbeat_at",
    ):
        next_payload.pop(key, None)
    if kind == "render":
        next_payload.pop("current_stage", None)
        next_payload.pop("current_substage", None)
        next_payload.setdefault("render_substage", "tts_prepare")
    return next_payload


def _retry_enqueue_for_kind(kind: str, project_id: int, payload: dict) -> tuple[RetryEnqueue, str]:
    if kind == "render":
        return lambda job_id: render_video.schedule(args=(job_id, project_id), delay=0), "渲染任务入队失败，请检查后台任务服务"
    if kind == "images":
        force = bool(payload.get("force", True))
        return lambda job_id: generate_project_images.schedule(args=(job_id, project_id), kwargs={"force": force}, delay=0), "智能生图任务入队失败，请检查后台任务服务"
    if kind == "scene_image":
        scene_id = int(payload.get("scene_id", 0) or 0)
        if scene_id <= 0:
            raise HTTPException(status_code=400, detail="缺少 scene_id，无法重试镜头生图任务")
        force = bool(payload.get("force", True))
        return lambda job_id: generate_scene_image.schedule(args=(job_id, scene_id), kwargs={"force": force}, delay=0), "单镜头生图任务入队失败，请检查后台任务服务"
    if kind == "tts_offline_install":
        voice_id = str(payload.get("voice_id", "") or "")
        return lambda job_id: tts_offline_install.schedule(args=(job_id,), kwargs={"voice_id": voice_id}, delay=0), "离线音色安装任务入队失败，请检查后台任务服务"
    if kind == "tts_offline_install_all_compatible":
        return lambda job_id: tts_offline_install_all_compatible.schedule(args=(job_id,), delay=0), "兼容音色安装任务入队失败，请检查后台任务服务"
    if kind == "autofill_media":
        prefer = str(payload.get("prefer", "video") or "video")
        return lambda job_id: autofill_media.schedule(args=(job_id, project_id), kwargs={"prefer": prefer}, delay=0), "自动补素材任务入队失败，请检查后台任务服务"
    if kind == "script_prepare":
        return lambda job_id: prepare_project_script.schedule(args=(job_id, project_id), delay=0), "文案生成任务入队失败，请检查后台任务服务"
    if kind == "autopilot":
        return lambda job_id: autopilot_run.schedule(args=(job_id, project_id), delay=0), "生成视频任务入队失败，请检查后台任务服务"
    raise HTTPException(status_code=400, detail=f"暂不支持重试该任务类型：{kind}")


def get_job_api(job_id: int) -> JobOut:
    with session_scope() as session:
        require_job_access(session, job_id)
    return job_out(job_id)


def list_jobs_api(limit: int = 100, project_id: int = 0) -> list[JobOut]:
    with session_scope() as session:
        query = select(Job)
        if project_id > 0:
            require_project_access(session, int(project_id))
            query = query.where(Job.project_id == int(project_id))
        elif current_principal() is not None and not bool(current_principal().get("is_admin")):
            all_project_ids = {int(pid) for pid in session.exec(select(Project.id)).all() if pid is not None}
            allowed_project_ids = visible_project_ids(session, all_project_ids)
            query = query.where(Job.project_id.in_(sorted(allowed_project_ids) or [-1]))
        items = session.exec(query.order_by(Job.created_at.desc()).limit(limit)).all()
        out: list[JobOut] = []
        project_ids = list({int(j.project_id) for j in items if j.project_id})
        proj_map: dict[int, Project] = {}
        if project_ids:
            proj_rows = session.exec(select(Project).where(Project.id.in_(project_ids))).all()
            proj_map = {int(p.id): p for p in proj_rows if p.id is not None}
        for j in items:
            if not j or j.id is None:
                continue
            p = proj_map.get(int(j.project_id)) if int(getattr(j, "project_id", 0) or 0) > 0 else None
            try:
                payload = json.loads(j.payload_json or "{}")
                if not isinstance(payload, dict):
                    payload = {}
            except Exception:
                payload = {}
            meta = job_error_meta(j)
            pipeline_run = get_pipeline_run(session, getattr(p, "current_pipeline_run_id", None)) if p else None
            current_stage, current_substage, render_substage = _job_stage_fields(j, payload, pipeline_run)
            out.append(
                JobOut(
                    id=int(j.id),
                    kind=j.kind,
                    project_id=j.project_id,
                    parent_job_id=(int(j.parent_job_id) if getattr(j, "parent_job_id", None) is not None else None),
                    root_job_id=(int(j.root_job_id) if getattr(j, "root_job_id", None) is not None else None),
                    retry_seq=int(getattr(j, "retry_seq", 0) or 0),
                    project_title=((p.title or "").strip() or None) if p else None,
                    project_workflow=((getattr(p, "workflow", "") or "").strip() or None) if p else None,
                    status=j.status,
                    progress=j.progress,
                    message=j.message,
                    payload_json=j.payload_json or "{}",
                    cancel_requested=bool(getattr(j, "cancel_requested", False)),
                    pause_requested=bool(getattr(j, "pause_requested", False)),
                    cancel_source=str(getattr(j, "cancel_source", "") or ""),
                    cancel_reason=str(getattr(j, "cancel_reason", "") or ""),
                    worker_id=str(getattr(j, "worker_id", "") or ""),
                    worker_pid=int(getattr(j, "worker_pid", 0) or 0),
                    worker_started_at=getattr(j, "worker_started_at", None),
                    worker_heartbeat_at=getattr(j, "worker_heartbeat_at", None),
                    current_stage=current_stage,
                    current_substage=current_substage,
                    render_substage=render_substage,
                    error_code=meta.get("error_code"),
                    blocking_component=meta.get("blocking_component"),
                    recommended_action=meta.get("recommended_action"),
                    recoverable=meta.get("recoverable"),
                    created_at=j.created_at,
                    updated_at=j.updated_at,
                )
            )
        return out


def batch_get_jobs_api(job_ids: list[int]) -> list[JobOut]:
    if not job_ids:
        return []
    with session_scope() as session:
        items = session.exec(select(Job).where(Job.id.in_(job_ids))).all()
        if current_principal() is not None and not bool(current_principal().get("is_admin")):
            allowed_project_ids = visible_project_ids(session, {int(j.project_id) for j in items if int(getattr(j, "project_id", 0) or 0) > 0})
            items = [j for j in items if int(getattr(j, "project_id", 0) or 0) in allowed_project_ids]
        out: list[JobOut] = []
        project_ids = list({int(j.project_id) for j in items if j.project_id})
        proj_map: dict[int, Project] = {}
        if project_ids:
            proj_rows = session.exec(select(Project).where(Project.id.in_(project_ids))).all()
            proj_map = {int(p.id): p for p in proj_rows if p.id is not None}
        for j in items:
            if not j or j.id is None:
                continue
            p = proj_map.get(int(j.project_id)) if int(getattr(j, "project_id", 0) or 0) > 0 else None
            try:
                payload = json.loads(j.payload_json or "{}")
                if not isinstance(payload, dict):
                    payload = {}
            except Exception:
                payload = {}
            meta = job_error_meta(j)
            pipeline_run = get_pipeline_run(session, getattr(p, "current_pipeline_run_id", None)) if p else None
            current_stage, current_substage, render_substage = _job_stage_fields(j, payload, pipeline_run)
            out.append(
                JobOut(
                    id=int(j.id),
                    kind=j.kind,
                    project_id=j.project_id,
                    parent_job_id=(int(j.parent_job_id) if getattr(j, "parent_job_id", None) is not None else None),
                    root_job_id=(int(j.root_job_id) if getattr(j, "root_job_id", None) is not None else None),
                    retry_seq=int(getattr(j, "retry_seq", 0) or 0),
                    project_title=((p.title or "").strip() or None) if p else None,
                    project_workflow=((getattr(p, "workflow", "") or "").strip() or None) if p else None,
                    status=j.status,
                    progress=j.progress,
                    message=j.message,
                    payload_json=j.payload_json or "{}",
                    cancel_requested=bool(getattr(j, "cancel_requested", False)),
                    pause_requested=bool(getattr(j, "pause_requested", False)),
                    cancel_source=str(getattr(j, "cancel_source", "") or ""),
                    cancel_reason=str(getattr(j, "cancel_reason", "") or ""),
                    worker_id=str(getattr(j, "worker_id", "") or ""),
                    worker_pid=int(getattr(j, "worker_pid", 0) or 0),
                    worker_started_at=getattr(j, "worker_started_at", None),
                    worker_heartbeat_at=getattr(j, "worker_heartbeat_at", None),
                    current_stage=current_stage,
                    current_substage=current_substage,
                    render_substage=render_substage,
                    error_code=meta.get("error_code"),
                    blocking_component=meta.get("blocking_component"),
                    recommended_action=meta.get("recommended_action"),
                    recoverable=meta.get("recoverable"),
                    created_at=j.created_at,
                    updated_at=j.updated_at,
                )
            )
        return out


def cancel_job_api(job_id: int) -> JobOut:
    with session_scope() as session:
        j = require_job_access(session, job_id)
        status = str(j.status or "").strip().lower()
        if status in ("done", "failed", "cancelled"):
            raise HTTPException(status_code=409, detail="当前任务状态不支持取消")
        delete_outputs_for_job(session, j)
    request_job_cancel(job_id, source="user", reason="用户取消任务")
    result = job_out(job_id)
    if int(getattr(result, 'project_id', 0) or 0) > 0:
        _refresh_projection(int(result.project_id))
    return result


def pause_job_api(job_id: int) -> JobOut:
    with session_scope() as session:
        j = require_job_access(session, job_id)
        status = str(j.status or "").strip().lower()
        if status not in ("queued", "running"):
            raise HTTPException(status_code=409, detail="当前任务状态不支持暂停")
    pause_job(job_id)
    result = job_out(job_id)
    if int(getattr(result, 'project_id', 0) or 0) > 0:
        _refresh_projection(int(result.project_id))
    return result


def resume_job_api(job_id: int) -> JobOut:
    with session_scope() as session:
        j = require_job_access(session, job_id)
        status = str(j.status or "").strip().lower()
        if status != "paused":
            raise HTTPException(status_code=409, detail="当前任务状态不支持继续")
    resume_job(job_id)
    result = job_out(job_id)
    if int(getattr(result, 'project_id', 0) or 0) > 0:
        _refresh_projection(int(result.project_id))
    return result


def delete_job_api(job_id: int) -> OkOut:
    project_id = 0
    with session_scope() as session:
        j = require_job_access(session, job_id)
        project_id = int(getattr(j, 'project_id', 0) or 0)
        status = str(j.status or "").strip().lower()
        if status in ACTIVE_JOB_STATUSES:
            raise HTTPException(status_code=409, detail="活动中的任务不能直接删除，请先取消或等待结束")
        delete_outputs_for_job(session, j)
        session.delete(j)
    if project_id > 0:
        _refresh_projection(project_id)
    return OkOut(ok=True)


def retry_job_api(job_id: int) -> JobCreateOut:
    with session_scope() as session:
        j = require_job_access(session, job_id)
        if str(j.status or "") in ACTIVE_JOB_STATUSES:
            raise HTTPException(status_code=409, detail="任务仍在进行中，不能直接重试")
        kind = j.kind
        project_id = int(j.project_id)
        try:
            payload = json.loads(j.payload_json or "{}")
        except Exception:
            payload = {}
        if project_id > 0 and kind != "autopilot":
            active_peer = session.exec(
                select(Job)
                .where(Job.project_id == project_id)
                .where(Job.kind == kind)
                .where(Job.status.in_(list(ACTIVE_JOB_STATUSES)))
                .order_by(Job.created_at.desc())
            ).first()
            if active_peer and active_peer.id is not None and int(active_peer.id) != int(j.id):
                raise HTTPException(status_code=409, detail=f"当前已有进行中的同类任务：{kind} · #{int(active_peer.id)}")
        delete_outputs_for_job(session, j)

    parent_job_id = int(j.id) if j and j.id is not None else None
    parent_root_job_id = int(getattr(j, "root_job_id", 0) or 0) if j else 0
    root_job_id = parent_root_job_id if parent_root_job_id > 0 else (parent_job_id or None)
    next_retry_seq = int(getattr(j, "retry_seq", 0) or 0) + 1 if j else 1

    if kind == "autopilot":
        with session_scope() as session:
            p = require_project_access(session, project_id)
            existing = latest_autopilot_job(session, project_id, active_only=True)
            if existing and existing.id is not None:
                return JobCreateOut(job=job_out(int(existing.id)))
        stage = autopilot_continue_stage(payload)
        next_payload = {**payload, "project_id": project_id}
        for key in (
            "error_code",
            "blocking_component",
            "recommended_action",
            "recoverable",
            "cancel_requested",
            "cancel_source",
            "cancel_reason",
            "pause_requested",
            "worker_id",
            "worker_pid",
            "worker_started_at",
            "worker_heartbeat_at",
        ):
            next_payload.pop(key, None)
        if stage:
            next_payload["resume_from_stage"] = stage
            next_payload["current_stage"] = stage
            if stage != "render":
                next_payload.pop("render_substage", None)
            job = enqueue_project_job(
                kind="autopilot",
                project_id=project_id,
                message=f"继续生成 · 从{stage}",
                payload=next_payload,
                parent_job_id=parent_job_id,
                root_job_id=root_job_id,
                retry_seq=next_retry_seq,
                enqueue=lambda next_job_id: autopilot_run.schedule(args=(next_job_id, project_id), delay=0),
                enqueue_error_message="继续生成任务入队失败，请检查后台任务服务",
            )
        else:
            next_payload.pop("resume_from_stage", None)
            job = enqueue_project_job(
                kind="autopilot",
                project_id=project_id,
                message="重新开始",
                payload=next_payload,
                parent_job_id=parent_job_id,
                root_job_id=root_job_id,
                retry_seq=next_retry_seq,
                enqueue=lambda next_job_id: autopilot_run.schedule(args=(next_job_id, project_id), delay=0),
                enqueue_error_message="重新开始任务入队失败，请检查后台任务服务",
            )
        return JobCreateOut(job=job)

    next_payload = _retry_payload_for_kind(kind, payload)
    enqueue, enqueue_error_message = _retry_enqueue_for_kind(kind, project_id, next_payload)
    job = enqueue_project_job(
        kind=kind,
        project_id=project_id,
        message="排队中",
        payload=next_payload,
        parent_job_id=parent_job_id,
        root_job_id=root_job_id,
        retry_seq=next_retry_seq,
        enqueue=enqueue,
        enqueue_error_message=enqueue_error_message,
    )
    if int(getattr(job, 'project_id', 0) or 0) > 0:
        _refresh_projection(int(job.project_id))
    return JobCreateOut(job=job)
