from app.schemas import AutopilotOut
from app.modules.pipeline.service import continue_pipeline_api, rerun_pipeline_api, start_pipeline_api


def start_autopilot_api(project_id: int) -> AutopilotOut:
    return start_pipeline_api(project_id)


def continue_autopilot_api(project_id: int) -> AutopilotOut:
    return continue_pipeline_api(project_id)


def rerun_autopilot_api(project_id: int) -> AutopilotOut:
    return rerun_pipeline_api(project_id)
