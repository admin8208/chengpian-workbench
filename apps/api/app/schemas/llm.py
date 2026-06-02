from typing import Optional

from pydantic import BaseModel


class LlmProviderOut(BaseModel):
    id: int
    name: str
    type: str
    base_url: str
    default_model: str
    enabled: bool
    is_default: bool
    api_key: str = ""


class LlmProviderIn(BaseModel):
    name: str
    type: str
    base_url: str
    default_model: str
    enabled: bool = True
    is_default: bool = False
    api_key: str = ""


class LlmProviderPatchIn(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    enabled: Optional[bool] = None
    is_default: Optional[bool] = None


class LlmKeyIn(BaseModel):
    api_key: str


class LlmStatusOut(BaseModel):
    has_default: bool
    default_provider_id: Optional[int] = None
    default_provider_name: Optional[str] = None
    default_provider_type: Optional[str] = None
    default_model: Optional[str] = None
    has_api_key: bool = False


class LlmTestIn(BaseModel):
    provider_id: Optional[int] = None
    type: Optional[str] = None
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    api_key: Optional[str] = None
    prompt: str = 'Return JSON: {"ok": true}'


class LlmTestOut(BaseModel):
    ok: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    message: Optional[str] = None
