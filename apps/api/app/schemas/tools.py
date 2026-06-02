from pydantic import BaseModel


class VideoToAudioOut(BaseModel):
    ok: bool = True
    filename: str
    mime: str = "audio/mpeg"
    size: int = 0
    url: str
    rel_path: str


class VideoUrlToAudioIn(BaseModel):
    url: str


class VideoToAudioProjectIn(BaseModel):
    title: str
    channel_key: str
    material_mode: str = "network"
    rel_path: str


class VideoToAudioProjectOut(BaseModel):
    ok: bool = True
    project_id: int
