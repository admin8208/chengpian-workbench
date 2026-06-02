from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from .scene import SceneOut


class ProjectCreateIn(BaseModel):
    title: str
    channel_key: str
    source_text: str = ""
    render_config: dict | None = None


class ProjectOut(BaseModel):
    id: int
    title: str
    workflow: str
    channel_key: str
    status: str
    script: str
    script_source: str = ""
    source_text: str = ""
    character_profile: str = ""
    publish_title: str = ""
    publish_hashtags: str = ""
    render_config: dict = {}
    voice_asset_id: Optional[int] = None
    subtitle_asset_id: Optional[int] = None
    confirmed_baseline_revision_id: Optional[int] = None
    current_pipeline_run_id: Optional[int] = None
    role_image_url: Optional[str] = None
    voice_url: Optional[str] = None
    subtitle_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ProjectDetailOut(ProjectOut):
    scenes: list[SceneOut]


class ProjectSummaryOut(BaseModel):
    project_id: int
    project_title: str
    workflow: str
    material_mode: str = "network"
    status: str
    confirmed_baseline_revision_id: Optional[int] = None
    current_pipeline_run_id: Optional[int] = None
    input_mode: str = "text"
    scene_count: int = 0
    missing_asset_count: int = 0
    review_count: int = 0
    duplicate_asset_count: int = 0
    final_exists: bool = False
    final_size: int = 0
    history_count: int = 0
    export_count: int = 0
    tts_backend: str = "auto"
    tts_backend_label: str = "自动"
    subtitle_style: str = "boxed"
    subtitle_style_label: str = "电影黑底字幕"
    last_job_kind: Optional[str] = None
    last_job_status: Optional[str] = None
    last_job_message: Optional[str] = None
    last_job_stage: Optional[str] = None
    continue_stage: Optional[str] = None
    suggestions: list[str] = []
    fix_actions: list[str] = []
    content_reasonableness_score: int = 0
    content_reasonableness_items: list[str] = []
    content_reasonableness_metrics: dict[str, int] = {}


class ProjectQualityOut(BaseModel):
    score: int
    issues: list[str] = []
    strengths: list[str] = []
    suggestions: list[str] = []
    metrics: dict[str, int] = {}
    platform_notes: dict[str, list[str]] = {}


class ProjectPatchIn(BaseModel):
    title: Optional[str] = None
    script: Optional[str] = None
    source_text: Optional[str] = None
    character_profile: Optional[str] = None
    publish_title: Optional[str] = None
    publish_hashtags: Optional[str] = None
    render_config: Optional[dict] = None
    voice_asset_id: Optional[int] = None
    subtitle_asset_id: Optional[int] = None


class ProjectScriptPrepareOut(BaseModel):
    ok: bool
    project: ProjectOut


class ProjectScriptConfirmIn(BaseModel):
    script: Optional[str] = None
