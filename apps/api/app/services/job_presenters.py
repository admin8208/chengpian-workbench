import json
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlmodel import Session, select

from app.db import session_scope
from app.job_control import finalize_cancelled_job_if_stale_in_session
from app.jobs import get_job_payload
from app.models import Asset, Job, Project, Scene, Variant
from app.modules.pipeline.repository import get_pipeline_run
from app.modules.pipeline.state import pipeline_stage_label
from app.project_paths import asset_disk_path, project_exports_dir
from app.schemas import JobOut


def _job_stage_fields(job: Job, payload: dict, pipeline_run) -> tuple[str | None, str | None, str | None]:
    kind = str(getattr(job, "kind", "") or "").strip().lower()
    render_substage = str(payload.get("render_substage") or "").strip().lower() or None
    if kind == "autopilot":
        return (
            pipeline_stage_label(pipeline_run, payload),
            str(payload.get("current_substage") or "").strip().lower() or None,
            render_substage,
        )
    if kind == "render":
        return ("render", None, render_substage)
    return (
        pipeline_stage_label(pipeline_run, payload),
        str(payload.get("current_substage") or "").strip().lower() or None,
        render_substage,
    )


def job_out(job_id: int) -> JobOut:
    with session_scope() as session:
        try:
            if isinstance(session, Session) or hasattr(session, "job"):
                finalize_cancelled_job_if_stale_in_session(session, int(job_id))
        except Exception:
            pass
        job = session.exec(select(Job).where(Job.id == job_id)).first()
        if not job:
            raise HTTPException(status_code=404, detail="任务不存在")
        resolved_job_id = int(job.id or 0)
        project_title = None
        project_workflow = None
        project = None
        try:
            if int(job.project_id or 0) > 0:
                project = session.exec(select(Project).where(Project.id == int(job.project_id))).first()
                if project and getattr(project, "title", None) is not None and getattr(project, "workflow", None) is not None:
                    project_title = (project.title or "").strip() or None
                    project_workflow = (getattr(project, "workflow", "") or "").strip() or None
                else:
                    project = None
        except Exception:
            project_title = None
            project_workflow = None
            project = None
        payload = get_job_payload(resolved_job_id) if resolved_job_id > 0 else {}
        pipeline_run = get_pipeline_run(session, getattr(project, "current_pipeline_run_id", None)) if project else None
        meta = job_error_meta(job)
        current_stage, current_substage, render_substage = _job_stage_fields(job, payload, pipeline_run)
        return JobOut(
            id=resolved_job_id,
            kind=job.kind,
            project_id=job.project_id,
            parent_job_id=(int(job.parent_job_id) if getattr(job, "parent_job_id", None) is not None else None),
            root_job_id=(int(job.root_job_id) if getattr(job, "root_job_id", None) is not None else None),
            retry_seq=int(getattr(job, "retry_seq", 0) or 0),
            project_title=project_title,
            project_workflow=project_workflow,
            status=job.status,
            progress=job.progress,
            message=job.message,
            payload_json=job.payload_json or "{}",
            cancel_requested=bool(getattr(job, "cancel_requested", False)),
            pause_requested=bool(getattr(job, "pause_requested", False)),
            cancel_source=str(getattr(job, "cancel_source", "") or ""),
            cancel_reason=str(getattr(job, "cancel_reason", "") or ""),
            worker_id=str(getattr(job, "worker_id", "") or ""),
            worker_pid=int(getattr(job, "worker_pid", 0) or 0),
            worker_started_at=getattr(job, "worker_started_at", None),
            worker_heartbeat_at=getattr(job, "worker_heartbeat_at", None),
            current_stage=current_stage,
            current_substage=current_substage,
            render_substage=render_substage,
            error_code=meta.get("error_code"),
            blocking_component=meta.get("blocking_component"),
            recommended_action=meta.get("recommended_action"),
            recoverable=meta.get("recoverable"),
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


def job_error_meta(job: Job | None) -> dict:
    payload: dict = {}
    try:
        payload = json.loads(getattr(job, "payload_json", "{}") or "{}") if job else {}
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}

    if not job or str(getattr(job, "status", "") or "").strip().lower() not in ("failed", "cancelled"):
        return {}

    error_code = str(payload.get("error_code") or "").strip().lower() or None
    blocking_component = str(payload.get("blocking_component") or "").strip().lower() or None
    recommended_action = str(payload.get("recommended_action") or "").strip().lower() or None
    recoverable_raw = payload.get("recoverable")
    recoverable = bool(recoverable_raw) if recoverable_raw is not None else None
    message = str(getattr(job, "message", "") or "")
    kind = str(getattr(job, "kind", "") or "").strip().lower()

    if not error_code:
        if any(text in message for text in ("未配置默认大模型", "API Key", "base_url", "model", "Provider")):
            error_code = "llm_config_missing"
        elif any(text in message for text in ("生图", "图片", "出图")) and any(text in message for text in ("API Key", "base_url", "model", "默认")):
            error_code = "image_config_missing"
        elif any(text in message for text in ("素材来源", "Pexels", "Pixabay")):
            error_code = "media_provider_unavailable"
        elif any(text in message for text in ("Edge TTS", "配音", "字幕")):
            error_code = "tts_unavailable"
        elif "项目不存在" in message:
            error_code = "project_missing"
        elif any(text in message for text in ("final.mp4", "渲染")):
            error_code = "render_failed"

    if not blocking_component:
        if error_code and error_code.startswith("llm_"):
            blocking_component = "llm"
        elif error_code and error_code.startswith("image_"):
            blocking_component = "image"
        elif error_code and error_code.startswith("media_"):
            blocking_component = "media"
        elif error_code and error_code.startswith("tts_"):
            blocking_component = "tts"
        elif error_code in ("render_failed", "final_missing", "promote_final_failed"):
            blocking_component = "render"
        elif error_code == "project_missing":
            blocking_component = "project"

    if not recommended_action:
        if error_code == "llm_config_missing" or (error_code and error_code.startswith("llm_")):
            recommended_action = "go_settings_llm"
        elif error_code == "image_config_missing":
            recommended_action = "go_settings_image"
        elif error_code == "media_provider_unavailable":
            recommended_action = "go_settings_media"
        elif error_code == "tts_unavailable":
            recommended_action = "go_settings_tts"
        elif error_code in ("render_failed", "final_missing", "promote_final_failed"):
            recommended_action = "render" if kind != "autopilot" else "continue_from_project"
        elif error_code == "project_missing":
            recommended_action = "open_project"

    if recoverable is None:
        recoverable = error_code not in (None, "project_missing")

    return {
        "error_code": error_code,
        "blocking_component": blocking_component,
        "recommended_action": recommended_action,
        "recoverable": recoverable,
    }


def _clear_scene_generated_image_binding(session: Session, *, asset_id: int) -> None:
    scenes = session.exec(select(Scene).where(Scene.image_asset_id == int(asset_id))).all()
    for scene in scenes:
        try:
            meta = json.loads(scene.meta_json or "{}") if str(scene.meta_json or "").strip() else {}
            if not isinstance(meta, dict):
                meta = {}
        except Exception:
            meta = {}
        scene.image_asset_id = None
        scene.status = "pending"
        for key in ("generated_asset_id", "preserved_previous_image"):
            meta.pop(key, None)
        meta["last_image_generation_failed"] = True
        meta["last_image_generation_error"] = "智能生图输出已删除，请重新生成当前镜头图片。"
        scene.meta_json = json.dumps(meta, ensure_ascii=True)
        session.add(scene)


def delete_outputs_for_job(session: Session, job: Job) -> None:
    if not job or job.id is None:
        return
    start = job.created_at
    end = job.updated_at
    start2 = start - timedelta(minutes=5)
    end2 = end + timedelta(minutes=10)
    kind = str(job.kind or "")
    pid = int(job.project_id or 0)
    payload: dict = {}
    try:
        payload = json.loads(job.payload_json or "{}")
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}

    def _asset_meta(asset: Asset) -> dict:
        try:
            obj = json.loads(getattr(asset, "meta_json", "{}") or "{}")
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    def _remove_asset_file(asset: Asset) -> None:
        rel = str(getattr(asset, "rel_path", "") or "").strip()
        if not rel:
            return
        path = asset_disk_path(rel, is_export=bool(str(asset.kind or "") == "video" and str(asset.tag or "") in ("export", "export_history")))
        try:
            if path.exists() and path.is_file():
                path.unlink(missing_ok=True)
        except Exception:
            pass

    if kind in ("render", "autopilot") and pid > 0:
        tags = ["export", "export_history"]
        candidate_batch_id = str(payload.get("candidate_batch_id") or payload.get("batch_id") or "").strip()
        rows = session.exec(
            select(Asset)
            .where(Asset.project_id == pid)
            .where(Asset.tag.in_(tags + ["voice_generated", "subtitle_generated"]))
        ).all()
        matched_assets: list[Asset] = []
        for asset in rows:
            meta = _asset_meta(asset)
            try:
                render_job_id = int(meta.get("render_job_id") or 0)
            except Exception:
                render_job_id = 0
            batch_id = str(meta.get("batch_id") or "").strip()
            if render_job_id == int(job.id) or (candidate_batch_id and batch_id and batch_id == candidate_batch_id):
                matched_assets.append(asset)

        for asset in matched_assets:
            if not asset or not asset.rel_path:
                continue
            _remove_asset_file(asset)
            try:
                session.delete(asset)
            except Exception:
                pass
        return

    if kind == "render" and pid > 0:
        vids = session.exec(
            select(Asset)
            .where(Asset.kind == "video")
            .where(Asset.project_id == pid)
            .where(Asset.tag.in_(["export", "export_history"]))
            .where(Asset.created_at >= start2)
            .where(Asset.created_at <= end2)
        ).all()
        for asset in vids:
            if not asset or not asset.rel_path:
                continue
            _remove_asset_file(asset)
            try:
                session.delete(asset)
            except Exception:
                pass
        final_path = (project_exports_dir(pid) / "final.mp4").resolve()
        try:
            if final_path.exists() and final_path.is_file():
                modified_at = datetime.utcfromtimestamp(final_path.stat().st_mtime)
                if start2 <= modified_at <= end2:
                    final_path.unlink()
        except Exception:
            pass

    if kind in ("images", "scene_image") and pid > 0:
        query = (
            select(Asset)
            .where(Asset.kind == "image")
            .where(Asset.project_id == pid)
            .where(Asset.tag == "scene_generated_ai")
            .where(Asset.created_at >= start2)
            .where(Asset.created_at <= end2)
        )
        if kind == "scene_image":
            try:
                scene_id = int(payload.get("scene_id", 0) or 0)
            except Exception:
                scene_id = 0
            if scene_id > 0:
                query = query.where(Asset.scene_id == scene_id)
        for asset in session.exec(query).all():
            if not asset or not asset.rel_path:
                continue
            if getattr(asset, "id", None) is not None:
                _clear_scene_generated_image_binding(session, asset_id=int(asset.id))
            _remove_asset_file(asset)
            try:
                session.delete(asset)
            except Exception:
                pass

    if kind == "ab_hooks" and pid > 0:
        for variant in session.exec(
            select(Variant)
            .where(Variant.project_id == pid)
            .where(Variant.kind == "ab_hook")
            .where(Variant.created_at >= start2)
            .where(Variant.created_at <= end2)
        ).all():
            try:
                session.delete(variant)
            except Exception:
                pass
