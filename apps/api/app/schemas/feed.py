from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class FeedTagOut(BaseModel):
    label: str
    type: Literal["info", "warning", "danger", "success"] = "info"


class ProjectFeedJobOut(BaseModel):
    id: int
    kind: str
    kind_label: str
    status: str
    status_label: str
    progress: int = 0
    stage_label: str = ""
    substage_label: str = ""
    stage_summary: str = ""
    message_label: str = ""
    hint: str = ""
    updated_at: datetime
    updated_at_text: str = ""
    resume_label: str = ""
    chain_attempts_label: str = ""


class ProjectCenterItemOut(BaseModel):
    project_id: int
    title: str
    workflow: str
    channel_key: str
    material_mode: str = "network"
    material_mode_label: str = "联网素材"
    open_path: str
    tone: Literal["", "success", "warning", "danger"] = ""
    status: str
    status_label: str
    stage_text: str
    notice: str
    action_key: Literal["open_project", "continue_project", "rerun_project"] = "open_project"
    action_label: str = "打开项目"
    tags: list[FeedTagOut] = []
    final_exists: bool = False
    emphasize_asset_issues: bool = False
    missing_asset_label: str = "缺素材"
    missing_asset_count: int = 0
    duplicate_asset_count: int = 0
    continue_stage_label: str = ""
    needs_llm_settings: bool = False
    needs_media_settings: bool = False
    needs_tts_settings: bool = False
    can_delete: bool = True
    updated_at: datetime
    updated_at_text: str = ""
    current_job: Optional[ProjectFeedJobOut] = None
    current_job_is_active: bool = False


class ProjectCenterStatsOut(BaseModel):
    all: int = 0
    running: int = 0
    failed: int = 0
    final_ready: int = 0


class ProjectCenterFeedOut(BaseModel):
    stats: ProjectCenterStatsOut
    items: list[ProjectCenterItemOut]
    server_time: datetime
    next_cursor: str = ""
    rebuilding: bool = False


class JobCenterHistoryItemOut(BaseModel):
    job_id: int
    execution_label: str = ""
    status: str
    status_label: str
    status_tone: Literal["info", "warning", "danger", "success"] = "info"
    stage_label: str = ""
    substage_label: str = ""
    updated_at: datetime
    updated_at_text: str = ""


class JobCenterItemOut(BaseModel):
    entry_key: str
    entry_type: Literal["chain", "job"]
    project_id: int
    project_title: str
    project_material_mode: str = "network"
    project_open_path: str
    project_final_exists: bool = False
    status: str
    status_label: str
    status_tone: Literal["info", "warning", "danger", "success"] = "info"
    job_id: int
    root_job_id: Optional[int] = None
    attempt_count: int = 1
    chain_attempts_label: str = ""
    job_kind: str
    job_kind_label: str
    stage_label: str = ""
    substage_label: str = ""
    message_label: str = ""
    human_hint: str = ""
    progress: int = 0
    updated_at: datetime
    updated_at_text: str = ""
    error_code: Optional[str] = None
    error_code_label: str = ""
    blocking_component: Optional[str] = None
    blocking_component_label: str = ""
    recommended_action: Optional[str] = None
    recommended_action_label: str = ""
    is_active: bool = False
    is_deletable: bool = False
    history: list[JobCenterHistoryItemOut] = []


class JobCenterStatsOut(BaseModel):
    all: int = 0
    active: int = 0
    failed: int = 0
    done: int = 0
    cancelled: int = 0


class JobCenterFeedOut(BaseModel):
    stats: JobCenterStatsOut
    items: list[JobCenterItemOut]
    server_time: datetime
    next_cursor: str = ""
    rebuilding: bool = False
