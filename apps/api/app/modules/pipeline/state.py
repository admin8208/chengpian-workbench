from __future__ import annotations

from app.models import Project
from app.models_revisions import PipelineRun


AUTOPILOT_STAGE_ALIASES = {
    "storyboard": "storyboard",
    "storyboard_plan": "storyboard",
    "media": "media",
    "visual_resolve": "media",
    "tts": "tts",
    "audio_subtitle_finalize": "tts",
    "render": "render",
    "render_finalize": "render",
}


def normalize_autopilot_stage(stage: str | None) -> str | None:
    raw = str(stage or "").strip().lower()
    return AUTOPILOT_STAGE_ALIASES.get(raw)


def is_autopilot_stage(stage: str | None) -> bool:
    return normalize_autopilot_stage(stage) is not None


def pipeline_stage_label(run: PipelineRun | None, payload: dict | None = None) -> str | None:
    obj = payload if isinstance(payload, dict) else {}
    stage = str(getattr(run, "current_stage", "") or obj.get("current_stage") or obj.get("last_failed_stage") or "").strip().lower()
    return stage or None


def pipeline_continue_stage(run: PipelineRun | None, payload: dict | None = None) -> str | None:
    obj = payload if isinstance(payload, dict) else {}
    stage = str(getattr(run, "resume_from_stage", "") or obj.get("resume_from_stage") or obj.get("last_failed_stage") or "").strip().lower()
    return normalize_autopilot_stage(stage)


def project_has_confirmed_baseline(project: Project | None) -> bool:
    return bool(getattr(project, "confirmed_baseline_revision_id", None))


def project_script_display_status(project: Project | None) -> str:
    if project_has_confirmed_baseline(project):
        return "confirmed"
    return "generated" if str(getattr(project, "script", "") or "").strip() else "empty"
