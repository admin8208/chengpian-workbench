from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AssetOut(BaseModel):
    id: int
    kind: str
    tag: str = ""
    project_id: Optional[int] = None
    scene_id: Optional[int] = None
    url: str
    mime: str = ""
    meta: dict = {}
    created_at: datetime


class LibraryImportIn(BaseModel):
    provider: str
    kind: str
    title: str = ""
    page_url: str
    file_url: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration_sec: Optional[float] = None
    thumb_url: Optional[str] = None
    preview_url: Optional[str] = None
    license_short: str = ""
    license_url: Optional[str] = None
    author: str = ""
    attribution: str = ""


class VideoImportIn(BaseModel):
    url: str


class LibraryListIn(BaseModel):
    kind: str = "image"
    query: str = ""
    limit: int = 60
