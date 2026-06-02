from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from app.time_utils import now_utc


def utcnow() -> datetime:
    return now_utc()


class ContentBaselineRevision(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    input_mode: str = Field(default="text", index=True)  # text|audio
    script_text: str = ""
    audio_asset_id: Optional[int] = Field(default=None, index=True)
    timing_json: str = "{}"
    source: str = ""  # llm|audio_transcribe|manual
    status: str = Field(default="draft", index=True)  # draft|confirmed|superseded
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class StoryboardRevision(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    baseline_revision_id: int = Field(index=True)
    material_mode: str = Field(default="network", index=True)  # network|ai
    status: str = Field(default="draft", index=True)  # draft|ready|stale|failed
    scene_count: int = 0
    meta_json: str = "{}"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class AudioSubtitleRevision(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    baseline_revision_id: int = Field(index=True)
    source: str = Field(default="tts", index=True)  # tts|audio_reuse
    status: str = Field(default="draft", index=True)  # draft|ready|stale|failed
    audio_asset_id: Optional[int] = Field(default=None, index=True)
    subtitle_asset_id: Optional[int] = Field(default=None, index=True)
    meta_json: str = "{}"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class PipelineRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    baseline_revision_id: Optional[int] = Field(default=None, index=True)
    storyboard_revision_id: Optional[int] = Field(default=None, index=True)
    status: str = Field(default="queued", index=True)  # queued|running|done|failed|cancelled
    current_stage: str = Field(default="baseline_prepare", index=True)
    current_substage: str = ""
    error_code: str = ""
    error_detail: str = ""
    resume_from_stage: str = ""
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
