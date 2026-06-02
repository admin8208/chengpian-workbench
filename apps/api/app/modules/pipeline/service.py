from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import text
from sqlmodel import select

from app.access_control import require_project_access
from app.api_common import autopilot_continue_stage, latest_autopilot_job
from app.db import session_scope
from app.job_dispatcher import enqueue_project_job
from app.jobs import get_job_payload
from app.llm_service import get_api_key, get_default_provider
from app.models import Project
from app.modules.baseline.repository import latest_confirmed_baseline
from app.modules.pipeline.repository import create_pipeline_run, fail_pipeline_run, get_pipeline_run
from app.modules.pipeline.state import project_has_confirmed_baseline
from app.modules.tts.service import tts_status_dict
from app.schemas import AutopilotOut
from app.tasks_autopilot import autopilot_preflight
from app.tasks_entries import autopilot_run


def _sanitize_resume_payload(payload: dict) -> dict:
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
    return next_payload


def _require_confirmed_script(project: Project) -> None:
    if not project_has_confirmed_baseline(project):
        raise HTTPException(status_code=409, detail="请先确认文案，再开始生成视频")


def start_pipeline_api(project_id: int) -> AutopilotOut:
    run_id: int | None = None
    with session_scope() as session:
        session.exec(text("SELECT pg_advisory_xact_lock(:lock_id)").bindparams(lock_id=int(project_id)))
        project = require_project_access(session, project_id)
        _require_confirmed_script(project)
        existing = latest_autopilot_job(session, project_id, active_only=True)
        if existing and existing.id is not None:
            from app.api_common import job_out

            return AutopilotOut(ok=True, jobs=[job_out(int(existing.id))])
        ok, meta = autopilot_preflight(session, project, resume_stage=None, get_default_provider=get_default_provider, get_api_key=get_api_key, tts_status_dict=tts_status_dict)
        if not ok:
            raise HTTPException(status_code=409, detail=str(meta.get("message") or "生成视频前置检查失败"))
        baseline = latest_confirmed_baseline(session, int(project.id))
        run = create_pipeline_run(
            session,
            project=project,
            baseline_revision_id=(int(baseline.id) if baseline and baseline.id is not None else None),
            storyboard_revision_id=None,
            current_stage="storyboard_plan",
        )
        run_id = int(run.id) if run.id is not None else None
    try:
        job = enqueue_project_job(
            kind="autopilot",
            project_id=project_id,
            message="排队中",
            payload={"project_id": project_id, "pipeline_run_id": run_id},
            enqueue=lambda job_id: autopilot_run.schedule(args=(job_id, project_id), delay=0),
            enqueue_error_message="生成视频任务入队失败，请检查后台任务服务",
        )
    except Exception as exc:
        with session_scope() as session:
            fail_pipeline_run(session, run_id, message=str(exc))
        raise
    return AutopilotOut(ok=True, jobs=[job])


def continue_pipeline_api(project_id: int) -> AutopilotOut:
    with session_scope() as session:
        session.exec(text("SELECT pg_advisory_xact_lock(:lock_id)").bindparams(lock_id=int(project_id)))
        project = require_project_access(session, project_id)
        _require_confirmed_script(project)
        existing = latest_autopilot_job(session, project_id, active_only=True)
        if existing and existing.id is not None:
            from app.api_common import job_out

            return AutopilotOut(ok=True, jobs=[job_out(int(existing.id))])
        prev = latest_autopilot_job(session, project_id, active_only=False)
        payload = get_job_payload(int(prev.id)) if prev and prev.id is not None else {}
        pipeline_run = get_pipeline_run(session, getattr(project, "current_pipeline_run_id", None))
        resume_stage = autopilot_continue_stage(payload, pipeline_run)
        ok, meta = autopilot_preflight(session, project, resume_stage=resume_stage, get_default_provider=get_default_provider, get_api_key=get_api_key, tts_status_dict=tts_status_dict)
        if not ok:
            raise HTTPException(status_code=409, detail=str(meta.get("message") or "继续生成前置检查失败"))
    if not resume_stage:
        return start_pipeline_api(project_id)
    next_payload = _sanitize_resume_payload({**payload, "project_id": project_id, "resume_from_stage": resume_stage, "current_stage": resume_stage})
    if resume_stage != "render":
        next_payload.pop("render_substage", None)
    parent_job_id = int(prev.id) if prev and prev.id is not None else None
    root_job_id = int(getattr(prev, "root_job_id", 0) or 0) if prev else 0
    if root_job_id <= 0:
        root_job_id = int(parent_job_id or 0)
    retry_seq = int(getattr(prev, "retry_seq", 0) or 0) + 1 if prev else 1
    job = enqueue_project_job(
        kind="autopilot",
        project_id=project_id,
        message=f"继续生成 · 从{resume_stage}",
        payload=next_payload,
        parent_job_id=parent_job_id,
        root_job_id=(root_job_id if root_job_id > 0 else None),
        retry_seq=retry_seq,
        enqueue=lambda job_id: autopilot_run.schedule(args=(job_id, project_id), delay=0),
        enqueue_error_message="继续生成任务入队失败，请检查后台任务服务",
    )
    return AutopilotOut(ok=True, jobs=[job])


def rerun_pipeline_api(project_id: int) -> AutopilotOut:
    with session_scope() as session:
        session.exec(text("SELECT pg_advisory_xact_lock(:lock_id)").bindparams(lock_id=int(project_id)))
        project = require_project_access(session, project_id)
        _require_confirmed_script(project)
        existing = latest_autopilot_job(session, project_id, active_only=True)
        if existing and existing.id is not None:
            raise HTTPException(status_code=409, detail="当前已有进行中的生成视频任务")
        ok, meta = autopilot_preflight(session, project, resume_stage=None, get_default_provider=get_default_provider, get_api_key=get_api_key, tts_status_dict=tts_status_dict)
        if not ok:
            raise HTTPException(status_code=409, detail=str(meta.get("message") or "重新生成前置检查失败"))
    job = enqueue_project_job(
        kind="autopilot",
        project_id=project_id,
        message="重新开始",
        payload=_sanitize_resume_payload({"project_id": project_id, "resume_from_stage": None}),
        enqueue=lambda job_id: autopilot_run.schedule(args=(job_id, project_id), delay=0),
        enqueue_error_message="重新开始任务入队失败，请检查后台任务服务",
    )
    return AutopilotOut(ok=True, jobs=[job])
