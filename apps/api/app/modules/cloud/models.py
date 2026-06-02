
"""Cloud storage configuration models."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from app.time_utils import now_utc


class CloudStorage(SQLModel, table=True):
    """Cloud storage configuration."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    storage_type: str
    config_json: str = "{}"
    is_default: bool = Field(default=False)
    enabled: bool = Field(default=True)
    last_sync_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)
