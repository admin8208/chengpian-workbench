from __future__ import annotations

from sqlmodel import select

from app.db import session_scope
from app.material_policies import project_material_mode
from app.models import Scene
from app.modules.visual.resolver import resolve_visual_pipeline


def _scene_narration_snapshot(project_id: int) -> dict[int, str]:
    with session_scope() as session:
        rows = session.exec(select(Scene).where(Scene.project_id == int(project_id)).order_by(Scene.idx)).all()
        return {int(row.id or 0): str(row.narration or "") for row in rows if row.id is not None}


def run_visual_stage(
    *,
    job_id: int,
    project_id: int,
    pid: int,
    wf: str,
    project,
    autofill_media_local,
    generate_images_local,
    autopilot_mark_stage,
    autopilot_get_job_status,
    autopilot_job_message,
    autopilot_payload,
    autopilot_scene_stats,
    humanize_autopilot_detail,
    update_job,
    wait_if_job_paused,
) -> None:
    before_narration = _scene_narration_snapshot(project_id)
    pipeline = resolve_visual_pipeline(project_material_mode(project))
    pipeline.run_media_stage(
        job_id=job_id,
        project_id=project_id,
        pid=pid,
        wf=wf,
        project=project,
        autofill_media_local=autofill_media_local,
        generate_images_local=generate_images_local,
        autopilot_mark_stage=autopilot_mark_stage,
        autopilot_get_job_status=autopilot_get_job_status,
        autopilot_job_message=autopilot_job_message,
        autopilot_payload=autopilot_payload,
        autopilot_scene_stats=autopilot_scene_stats,
        humanize_autopilot_detail=humanize_autopilot_detail,
        update_job=update_job,
        wait_if_job_paused=wait_if_job_paused,
    )
    after_narration = _scene_narration_snapshot(project_id)
    for scene_id, narration in before_narration.items():
        if scene_id in after_narration and after_narration[scene_id] != narration:
            raise RuntimeError("视觉阶段不得改写主旁白，请重新生成主时间轴后再继续。")
