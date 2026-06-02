from app.services.autopilot_state import (
    autopilot_continue_stage,
    get_project_workflow_meta,
    latest_autopilot_job,
    project_autopilot_mode,
)
from app.services.job_presenters import delete_outputs_for_job, job_error_meta, job_out
from app.services.project_outputs import (
    cleanup_project_intermediate_artifacts,
    resolve_final_export_status,
    stable_final_export_status,
)
from app.services.project_quality import check_render_quality
from app.services.project_storage import (
    ensure_project_storage_clean,
    project_storage_dir_specs,
    project_storage_leftovers,
    remove_project_storage_strict,
    safe_rmtree,
    safe_unlink,
)
from app.services.render_defaults import (
    default_render_dimensions,
    default_visual_strategy_for_channel,
    normalize_render_aspect,
    project_render_aspect,
    project_visual_strategy,
)
from app.services.tts_cache_registry import (
    cleanup_project_tts_cache_refs,
    cleanup_unreferenced_tts_cache,
    register_project_tts_cache_refs,
)
from app.settings import settings


def resolve_final_export_status(session, project_id: int) -> dict:
    from app.services import project_outputs as _project_outputs

    original_settings = _project_outputs.settings
    try:
        _project_outputs.settings = settings
        return _project_outputs.resolve_final_export_status(session, project_id)
    finally:
        _project_outputs.settings = original_settings


PROTECTED_JOB_KINDS = {"tts_offline_install", "tts_offline_install_all_compatible"}
