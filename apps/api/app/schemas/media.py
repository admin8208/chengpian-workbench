from typing import Literal, Optional

from pydantic import BaseModel


class WebMediaItemOut(BaseModel):
    provider: str
    kind: str
    title: str
    page_url: str
    file_url: str
    thumb_url: Optional[str] = None
    preview_url: Optional[str] = None
    mime: str = ""
    width: Optional[int] = None
    height: Optional[int] = None
    duration_sec: Optional[float] = None
    license_short: str = ""
    license_url: Optional[str] = None
    author: str = ""
    attribution: str = ""


class WebSearchOut(BaseModel):
    ok: bool
    items: list[WebMediaItemOut]


class MediaKeyIn(BaseModel):
    api_key: str


class MediaProviderStatusOut(BaseModel):
    provider: str
    has_api_key: bool = False
    api_key: str = ""
    ok: bool = True
    detail: Optional[str] = None
    supported_kinds: list[str] = []


class MediaProviderTestIn(BaseModel):
    kind: str = "image"
    query: str = "cat"
    limit: int = 5
    aspect: Literal["landscape", "portrait"] = "landscape"


class MediaProviderTestOut(BaseModel):
    ok: bool
    items: list[WebMediaItemOut] = []
    error: Optional[str] = None
