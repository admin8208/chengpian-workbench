
import json
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from app.time_utils import now_utc


def utcnow() -> datetime:
    return now_utc()


class ChannelPack(SQLModel, table=True):
    key: str = Field(primary_key=True)
    name: str
    description: str = ""
    config_json: str = "{}"  # JSON string
    created_at: datetime = Field(default_factory=utcnow)

    def config(self) -> dict:
        try:
            return json.loads(self.config_json or "{}")
        except Exception:
            return {}


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    owner_user_id: Optional[int] = Field(default=None, index=True)
    owner_username: str = Field(default="", index=True)
    workflow: str = Field(default="mix", index=True)  # mix
    channel_key: str = Field(index=True)
    status: str = Field(default="draft", index=True)  # draft|processing|ready|failed
    script: str = ""
    script_source: str = ""  # llm|audio_transcribe|manual
    source_text: str = ""  # optional paste-in text for rewriting
    character_profile: str = ""  # optional character/persona notes
    publish_title: str = ""  # optional override for publish pack
    publish_hashtags: str = ""  # optional override for publish pack
    role_image_asset_id: Optional[int] = Field(default=None, index=True)
    voice_asset_id: Optional[int] = Field(default=None, index=True)
    subtitle_asset_id: Optional[int] = Field(default=None, index=True)
    confirmed_baseline_revision_id: Optional[int] = Field(default=None, index=True)
    current_pipeline_run_id: Optional[int] = Field(default=None, index=True)
    render_config_json: str = "{}"  # JSON string (per-project overrides)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    def render_config(self) -> dict:
        try:
            obj = json.loads(self.render_config_json or "{}")
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}


class Asset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str = Field(index=True)  # image|audio|video|other
    rel_path: str  # relative path under data_dir
    mime: str = ""
    project_id: Optional[int] = Field(default=None, index=True)
    scene_id: Optional[int] = Field(default=None, index=True)
    tag: str = Field(default="", index=True)
    meta_json: str = "{}"  # JSON string (source/licensing/etc)
    created_at: datetime = Field(default_factory=utcnow)


class Scene(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    storyboard_revision_id: Optional[int] = Field(default=None, index=True)
    idx: int = Field(index=True)
    narration: str = ""
    # For MIX workflow: a short, searchable query for stock footage / photos.
    media_query: str = ""
    image_prompt: str = ""
    image_negative: str = ""
    duration_sec: float = 4.0
    image_asset_id: Optional[int] = Field(default=None, index=True)
    meta_json: str = "{}"  # JSON string (visual/search metadata)
    status: str = Field(default="pending", index=True)  # pending|ready|failed
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str = Field(index=True)  # storyboard|render
    project_id: int = Field(index=True)
    parent_job_id: Optional[int] = Field(default=None, index=True)
    root_job_id: Optional[int] = Field(default=None, index=True)
    retry_seq: int = Field(default=0, index=True)
    status: str = Field(default="queued", index=True)  # queued|running|done|failed
    progress: int = Field(default=0)
    message: str = ""
    payload_json: str = "{}"  # JSON string
    cancel_requested: bool = Field(default=False, index=True)
    pause_requested: bool = Field(default=False, index=True)
    cancel_source: str = ""
    cancel_reason: str = ""
    worker_id: str = ""
    worker_pid: int = 0
    worker_started_at: Optional[datetime] = None
    worker_heartbeat_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class AppConfig(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str = ""  # small string value (single-user)
    updated_at: datetime = Field(default_factory=utcnow)


class UserAccount(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    password_hash: str
    password_salt: str
    enabled: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class LlmProvider(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    type: str = Field(index=True)  # openai_compat|ollama
    base_url: str
    default_model: str
    enabled: bool = True
    is_default: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Secret(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    provider_id: int = Field(index=True)
    name: str = Field(index=True)  # api_key
    value_enc: str
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ImageProvider(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    type: str = Field(index=True)  # openai_compat
    base_url: str
    default_model: str
    enabled: bool = True
    is_default: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ImageSecret(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    provider_id: int = Field(index=True)
    name: str = Field(index=True)  # api_key
    value_enc: str
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class MediaSecret(SQLModel, table=True):
    """Encrypted secrets for media providers (pexels/pixabay/etc)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    provider: str = Field(index=True)  # pexels|pixabay|...
    name: str = Field(index=True)  # api_key
    value_enc: str
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Variant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(index=True)
    kind: str = Field(index=True)  # ab_hook
    name: str = ""
    data_json: str = "{}"  # JSON string
    created_at: datetime = Field(default_factory=utcnow)


class ProjectCenterProjection(SQLModel, table=True):
    project_id: int = Field(primary_key=True)
    payload_json: str = "{}"
    updated_at: datetime = Field(default_factory=utcnow, index=True)


class JobCenterProjection(SQLModel, table=True):
    entry_key: str = Field(primary_key=True)
    payload_json: str = "{}"
    project_id: int = Field(default=0, index=True)
    job_kind: str = Field(default="", index=True)
    status: str = Field(default="", index=True)
    is_active: bool = Field(default=False, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)
