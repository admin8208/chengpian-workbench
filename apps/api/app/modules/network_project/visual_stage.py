from __future__ import annotations

from app.db import session_scope
from app.jobs import patch_job_payload
from app.models import Scene
from app.modules.media.service import has_media_api_key
from sqlmodel import select

def run_network_visual_stage(
    *,
    job_id: int,
    project_id: int,
    pid: int,
    wf: str,
    autofill_media_local,
    autopilot_mark_stage,
    autopilot_get_job_status,
    autopilot_job_message,
    autopilot_payload,
    autopilot_scene_stats,
    humanize_autopilot_detail,
    update_job,
    wait_if_job_paused,
) -> None:
    if wf != "mix":
        update_job(job_id, progress=50, message="生成视频：准备渲染")
        autopilot_mark_stage(job_id, "media", status="done")
        return
    autopilot_mark_stage(job_id, "media", status="running", progress=40, message="生成视频：自动匹配素材", substage="media_round_1")
    with session_scope() as session:
        has_any = has_media_api_key(session, "pexels") or has_media_api_key(session, "pixabay")
    if not has_any:
        update_job(job_id, progress=39, message="未配置商业素材源，先使用 Wikimedia 自动补素材（建议后续补 Pexels/Pixabay 提升画面质量）")
    rounds: list[tuple[int, str, int, int, str]] = [(40, "生成视频：自动匹配素材", 40, 22, "video"), (53, "", 53, 7, "image"), (60, "", 60, 6, "video"), (66, "", 66, 4, "image")]
    for idx, (progress, message, base, span, prefer) in enumerate(rounds, start=1):
        if idx > 4:
            break
        if idx > 1:
            missing_count, _review, total = autopilot_scene_stats(pid)
            if missing_count <= 0:
                break
            if idx == 2:
                patch_job_payload(job_id, {"current_substage": "media_round_2"})
                message = f"生成视频：自动补素材（第2轮，缺{missing_count}/{max(1, total)}）"
            elif idx == 3:
                patch_job_payload(job_id, {"current_substage": "media_round_3"})
                message = f"生成视频：自动补素材（第3轮，缺{missing_count}/{max(1, total)}）"
            else:
                patch_job_payload(job_id, {"current_substage": "media_repair"})
                message = f"生成视频：质量修复补素材（第4轮，缺{missing_count}/{max(1, total)}）"
        elif idx == 1:
            patch_job_payload(job_id, {"current_substage": "media_round_1"})
        update_job(job_id, progress=progress, message=message)
        wait_if_job_paused(job_id)
        autofill_kwargs = dict(prefer=prefer, outer_job_id=job_id, progress_base=base, progress_span=span, keep_running=True)
        autofill_media_local(job_id, project_id, **autofill_kwargs)
        if autopilot_get_job_status(job_id) in ("failed", "cancelled"):
            detail = autopilot_job_message(job_id).strip()
            if not detail:
                detail = str(autopilot_payload(job_id).get("last_error") or "").strip()
            if not detail:
                detail = "media_stage_interrupted"
            raise RuntimeError(detail)
    try:
        unresolved_count = 0
        with session_scope() as session:
            scenes = list(session.exec(select(Scene).where(Scene.project_id == int(project_id)).order_by(Scene.idx)).all())
            for scene in scenes:
                if not getattr(scene, "image_asset_id", None):
                    unresolved_count += 1
    except Exception:
        unresolved_count = 0
    if unresolved_count:
        detail = f"仍有 {unresolved_count} 个镜头缺少可用素材，请先补素材后继续。"
        autopilot_mark_stage(job_id, "media", status="failed", detail=detail, progress=68, message=f"生成视频：素材自动收口未完成（仍缺 {unresolved_count} 个镜头）", substage="media_verify")
        raise RuntimeError(humanize_autopilot_detail(detail))
    autopilot_mark_stage(job_id, "media", status="done", substage="media_verify")
