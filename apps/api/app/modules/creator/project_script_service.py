from app.schemas import ProjectOut
from app.modules.baseline.service import confirm_project_script, prepare_project_script, start_prepare_project_script_api


def prepare_project_script_api(project_id: int, *, project_to_out) -> ProjectOut:
    return prepare_project_script(project_id, project_to_out=project_to_out)


def start_prepare_project_script_job_api(project_id: int):
    return start_prepare_project_script_api(project_id)


def confirm_project_script_api(project_id: int, *, script: str | None, project_to_out) -> ProjectOut:
    return confirm_project_script(project_id, script=script, project_to_out=project_to_out)
