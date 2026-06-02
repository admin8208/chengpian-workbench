from __future__ import annotations

from app.db import session_scope
from app.models import Scene
from sqlmodel import select

def run_ai_visual_stage(
    *,
    job_id: int,
    project_id: int,
    pid: int,
    wf: str,
    generate_images_local,
    autopilot_mark_stage,
    autopilot_get_job_status,
    autopilot_job_message,
    autopilot_payload,
    humanize_autopilot_detail,
    update_job,
    wait_if_job_paused,
) -> None:
    if wf != "mix":
        update_job(job_id, progress=50, message="生成视频：准备渲染")
        autopilot_mark_stage(job_id, "media", status="done")
        return
    autopilot_mark_stage(job_id, "media", status="running", progress=40, message="生成视频：生成镜头图片", substage="generate_images")
    wait_if_job_paused(job_id)
    generate_images_local(job_id, project_id, force=False, manage_job_state=False)
    if autopilot_get_job_status(job_id) in ("failed", "cancelled"):
        detail = autopilot_job_message(job_id).strip()
        if not detail:
            detail = str(autopilot_payload(job_id).get("last_error") or "").strip()
        if not detail:
            detail = "image_generation_interrupted"
        raise RuntimeError(humanize_autopilot_detail(detail))
    unresolved_count = 0
    try:
        with session_scope() as session:
            scenes = list(session.exec(select(Scene).where(Scene.project_id == int(project_id)).order_by(Scene.idx)).all())
            for scene in scenes:
                if not getattr(scene, "image_asset_id", None):
                    unresolved_count += 1
    except Exception:
        unresolved_count = 0
    if unresolved_count:
        detail = f"仍有 {unresolved_count} 个镜头未生成图片，请先补齐后继续。"
        autopilot_mark_stage(job_id, "media", status="failed", detail=detail, progress=68, message=f"生成视频：智能生图未完成（仍缺 {unresolved_count} 个镜头）", substage="verify_images")
        raise RuntimeError(detail)
    autopilot_mark_stage(job_id, "media", status="done", progress=66, message="生成视频：镜头图片已生成", substage="verify_images")
