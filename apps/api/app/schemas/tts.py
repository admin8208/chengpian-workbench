from typing import Optional

from pydantic import BaseModel


class TtsPreviewIn(BaseModel):
    text: str
    voice: str
    rate: str = "+0%"
    volume: float = 1.0
    backend: Optional[str] = None
    offline_voice_id: Optional[str] = None


class TtsPreviewOut(BaseModel):
    ok: bool
    url: Optional[str] = None
    error: Optional[str] = None


class TtsStatusOut(BaseModel):
    backend: str
    offline_voice_id: str
    edge_voice_id: str = "zh-CN-XiaoxiaoNeural"
    default_voice_rate: str = "+0%"
    edge_synthesis_ok: bool
    edge_checked: bool = False
    edge_detail: str = ""
    offline_installed: bool
    offline_ok: bool
    offline_detail: str = ""
    offline_installed_voice_ids: list[str] = []
    offline_installed_voice_count: int = 0
    available_offline_voice_ids: list[str] = []
    available_offline_voice_count: int = 0
    available_offline_voices: list[dict] = []
    available_edge_voice_ids: list[str] = []
    available_edge_voice_count: int = 0
    available_edge_zh_cn_voice_count: int = 0
    available_edge_voices: list[dict] = []


class TtsBackendIn(BaseModel):
    backend: str = "auto"
    offline_voice_id: Optional[str] = None
    edge_voice_id: Optional[str] = None
    default_voice_rate: Optional[str] = None
