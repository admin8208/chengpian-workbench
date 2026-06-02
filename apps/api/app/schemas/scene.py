from typing import Optional

from pydantic import BaseModel


class SceneOut(BaseModel):
    id: int
    project_id: int
    idx: int
    narration: str
    media_query: str = ""
    image_prompt: str
    image_negative: str = ""
    duration_sec: float
    image_asset_id: Optional[int]
    image_url: Optional[str] = None
    meta: dict = {}
    status: str


class ScenePatchIn(BaseModel):
    narration: Optional[str] = None
    media_query: Optional[str] = None
    image_prompt: Optional[str] = None
    image_negative: Optional[str] = None
    duration_sec: Optional[float] = None
    meta: Optional[dict] = None


class SceneBindAssetIn(BaseModel):
    asset_id: int


class SceneSuggestIn(BaseModel):
    provider: str = "pexels"
    kind: str = "video"
    limit: int = 12
