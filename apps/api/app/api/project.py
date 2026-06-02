from fastapi import APIRouter

from app.api_common import autopilot_continue_stage, job_out, latest_autopilot_job
from app.application.projects import get_project_detail_api, get_project_quality_api, get_project_runtime_api, get_project_summary_api
from app.application.projects import confirm_project_script_api, continue_autopilot_api, create_project_api, delete_project_api, list_projects_api, patch_project_api, prepare_project_script_api, rerun_autopilot_api, start_autopilot_api, start_prepare_project_script_job_api
from app.presenters import project_to_out, scene_to_out
from app.schemas import AutopilotOut, JobCreateOut, OkOut, ProjectCreateIn, ProjectDetailOut, ProjectOut, ProjectPatchIn, ProjectQualityOut, ProjectRuntimeOut, ProjectScriptConfirmIn, ProjectSummaryOut
from app.subtitles import normalize_subtitle_settings

router = APIRouter(tags=["project"])


def _project_to_out_entry(session, p):
    return project_to_out(session, p)


def _scene_to_out_entry(session, s):
    return scene_to_out(session, s)


def _project_summary_cb(*args, **kwargs):
    from app.application.projects import project_summary_and_quality

    return project_summary_and_quality(
        *args,
        latest_autopilot_job=latest_autopilot_job,
        autopilot_continue_stage=autopilot_continue_stage,
        **kwargs,
    )


@router.get("/api/projects", response_model=list[ProjectOut])
def list_projects(workflow: str = ""):
    return list_projects_api(_project_to_out_entry, workflow)


@router.post("/api/projects", response_model=ProjectOut)
def create_project(body: ProjectCreateIn):
    return create_project_api(_project_to_out_entry, body, normalize_subtitle_settings=normalize_subtitle_settings)


@router.get("/api/projects/{project_id}", response_model=ProjectDetailOut)
def get_project(project_id: int):
    return get_project_detail_api(project_id, scene_to_out=_scene_to_out_entry, project_to_out=_project_to_out_entry)


@router.delete("/api/projects/{project_id}", response_model=OkOut)
def delete_project(project_id: int):
    return delete_project_api(project_id)


@router.get("/api/projects/{project_id}/summary", response_model=ProjectSummaryOut)
def get_project_summary(project_id: int):
    return get_project_summary_api(project_id, project_summary_and_quality_cb=_project_summary_cb)


@router.get("/api/projects/{project_id}/runtime", response_model=ProjectRuntimeOut)
def get_project_runtime(project_id: int):
    return get_project_runtime_api(project_id, project_summary_and_quality_cb=_project_summary_cb)


@router.get("/api/projects/{project_id}/quality", response_model=ProjectQualityOut)
def get_project_quality(project_id: int):
    return get_project_quality_api(project_id, project_summary_and_quality_cb=_project_summary_cb)


@router.patch("/api/projects/{project_id}", response_model=ProjectOut)
def patch_project(project_id: int, body: ProjectPatchIn):
    return patch_project_api(project_id, body, project_to_out=project_to_out, normalize_subtitle_settings=normalize_subtitle_settings)


@router.post("/api/projects/{project_id}/script", response_model=JobCreateOut)
def prepare_project_script(project_id: int):
    return {"job": start_prepare_project_script_job_api(project_id)}


@router.post("/api/projects/{project_id}/script/confirm", response_model=ProjectOut)
def confirm_project_script(project_id: int, body: ProjectScriptConfirmIn):
    return confirm_project_script_api(project_id, script=body.script, project_to_out=_project_to_out_entry)


@router.post("/api/projects/{project_id}/autopilot", response_model=AutopilotOut)
def start_autopilot(project_id: int):
    return start_autopilot_api(project_id)


@router.post("/api/projects/{project_id}/autopilot/continue", response_model=AutopilotOut)
def continue_autopilot(project_id: int):
    return continue_autopilot_api(project_id)


@router.post("/api/projects/{project_id}/autopilot/rerun", response_model=AutopilotOut)
def rerun_autopilot(project_id: int):
    return rerun_autopilot_api(project_id)
