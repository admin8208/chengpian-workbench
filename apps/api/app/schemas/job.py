from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class JobOut(BaseModel):
    id: int
    kind: str
    project_id: int
    parent_job_id: Optional[int] = None
    root_job_id: Optional[int] = None
    retry_seq: int = 0
    project_title: Optional[str] = None
    project_workflow: Optional[str] = None
    status: str
    progress: int
    message: str
    payload_json: str = "{}"
    cancel_requested: bool = False
    pause_requested: bool = False
    cancel_source: str = ""
    cancel_reason: str = ""
    worker_id: str = ""
    worker_pid: int = 0
    worker_started_at: Optional[datetime] = None
    worker_heartbeat_at: Optional[datetime] = None
    current_stage: Optional[str] = None
    current_substage: Optional[str] = None
    render_substage: Optional[str] = None
    error_code: Optional[str] = None
    blocking_component: Optional[str] = None
    recommended_action: Optional[str] = None
    recoverable: Optional[bool] = None
    created_at: datetime
    updated_at: datetime


class JobCreateOut(BaseModel):
    job: JobOut


class ProjectRuntimeOut(BaseModel):
    project_id: int
    project_title: str
    workflow: str
    material_mode: str = "network"
    project_status: str
    confirmed_baseline_revision_id: Optional[int] = None
    current_pipeline_run_id: Optional[int] = None
    workflow_stage: Optional[str] = None
    continue_stage: Optional[str] = None
    active_job_status: Optional[str] = None
    next_action: str = "open_project"
    last_job_kind: Optional[str] = None
    last_job_status: Optional[str] = None
    last_job_message: Optional[str] = None
    final_exists: bool = False
    missing_asset_count: int = 0
    review_count: int = 0
    duplicate_asset_count: int = 0
    blocker_items: list[str] = []
    suggested_fix_actions: list[str] = []
    summary_suggestions: list[str] = []
    current_job: Optional[JobOut] = None
    summary_job: Optional[JobOut] = None


class AutopilotOut(BaseModel):
    ok: bool = True
    jobs: list[JobOut]


class RenderBatchIn(BaseModel):
    count: int = 4
    mode: str = "quick"


class RenderBatchOut(BaseModel):
    jobs: list[JobOut]
