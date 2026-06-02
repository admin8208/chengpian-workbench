from __future__ import annotations

from app.material_policies import normalize_material_mode
from app.modules.ai_project.preflight import ai_media_preflight
from app.modules.ai_project.visual_stage import run_ai_visual_stage
from app.modules.network_project.preflight import network_media_preflight
from app.modules.network_project.visual_stage import run_network_visual_stage
from app.modules.visual.types import VisualPipeline


class _AiVisualPipeline:
    def media_preflight(self, session, project=None) -> tuple[bool, dict]:
        return ai_media_preflight(session, project=project)

    def run_media_stage(self, **kwargs) -> None:
        run_ai_visual_stage(
            job_id=kwargs["job_id"],
            project_id=kwargs["project_id"],
            pid=kwargs["pid"],
            wf=kwargs["wf"],
            generate_images_local=kwargs["generate_images_local"],
            autopilot_mark_stage=kwargs["autopilot_mark_stage"],
            autopilot_get_job_status=kwargs["autopilot_get_job_status"],
            autopilot_job_message=kwargs["autopilot_job_message"],
            autopilot_payload=kwargs["autopilot_payload"],
            humanize_autopilot_detail=kwargs["humanize_autopilot_detail"],
            update_job=kwargs["update_job"],
            wait_if_job_paused=kwargs["wait_if_job_paused"],
        )


class _NetworkVisualPipeline:
    def media_preflight(self, session, project=None) -> tuple[bool, dict]:
        return network_media_preflight(session, project=project)

    def run_media_stage(self, **kwargs) -> None:
        run_network_visual_stage(
            job_id=kwargs["job_id"],
            project_id=kwargs["project_id"],
            pid=kwargs["pid"],
            wf=kwargs["wf"],
            autofill_media_local=kwargs["autofill_media_local"],
            autopilot_mark_stage=kwargs["autopilot_mark_stage"],
            autopilot_get_job_status=kwargs["autopilot_get_job_status"],
            autopilot_job_message=kwargs["autopilot_job_message"],
            autopilot_payload=kwargs["autopilot_payload"],
            autopilot_scene_stats=kwargs["autopilot_scene_stats"],
            humanize_autopilot_detail=kwargs["humanize_autopilot_detail"],
            update_job=kwargs["update_job"],
            wait_if_job_paused=kwargs["wait_if_job_paused"],
        )


_AI_PIPELINE = _AiVisualPipeline()
_NETWORK_PIPELINE = _NetworkVisualPipeline()


def resolve_visual_pipeline(material_mode: str) -> VisualPipeline:
    return _AI_PIPELINE if normalize_material_mode(material_mode) == "ai" else _NETWORK_PIPELINE
