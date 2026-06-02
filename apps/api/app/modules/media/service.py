
from sqlmodel import select

from app.models import MediaSecret
from app.secrets import decrypt_str, encrypt_str
from app.time_utils import now_utc


def _norm_provider(provider: str) -> str:
    return (provider or "").strip().lower()


def upsert_media_api_key(session, provider: str, api_key: str) -> None:
    provider = _norm_provider(provider)
    if not provider:
        raise ValueError("provider is empty")
    enc = encrypt_str((api_key or "").strip())

    existing = session.exec(
        select(MediaSecret).where(MediaSecret.provider == provider).where(MediaSecret.name == "api_key")
    ).first()
    if existing:
        existing.value_enc = enc
        existing.updated_at = now_utc()
        session.add(existing)
    else:
        session.add(MediaSecret(provider=provider, name="api_key", value_enc=enc))


def has_media_api_key(session, provider: str) -> bool:
    provider = _norm_provider(provider)
    if not provider:
        return False
    s = session.exec(
        select(MediaSecret).where(MediaSecret.provider == provider).where(MediaSecret.name == "api_key")
    ).first()
    return bool(s and (s.value_enc or "").strip())


def get_media_api_key(session, provider: str) -> str:
    provider = _norm_provider(provider)
    if not provider:
        return ""
    s = session.exec(
        select(MediaSecret).where(MediaSecret.provider == provider).where(MediaSecret.name == "api_key")
    ).first()
    if not s or not s.value_enc:
        return ""
    return decrypt_str(s.value_enc)
