
from sqlalchemy import asc
from sqlmodel import select

from app.models import ImageProvider, ImageSecret
from app.secrets import decrypt_str, encrypt_str
from app.time_utils import now_utc


def get_default_image_provider(session) -> ImageProvider | None:
    p = session.exec(
        select(ImageProvider).where(ImageProvider.is_default == True)  # noqa: E712
    ).first()
    if p and p.enabled:
        return p
    return session.exec(select(ImageProvider).where(ImageProvider.enabled == True).order_by(asc(ImageProvider.id))).first()  # noqa: E712


def list_available_image_providers(session) -> list[ImageProvider]:
    items = session.exec(select(ImageProvider).where(ImageProvider.enabled == True).order_by(asc(ImageProvider.id))).all()  # noqa: E712
    default_id = 0
    for item in items:
        try:
            if bool(getattr(item, 'is_default', False)) and getattr(item, 'id', None) is not None:
                default_id = int(item.id)
                break
        except Exception:
            continue
    valid: list[ImageProvider] = []
    for item in items:
        provider_id = getattr(item, 'id', None)
        if provider_id is None:
            continue
        if not str(getattr(item, 'base_url', '') or '').strip():
            continue
        if not str(getattr(item, 'default_model', '') or '').strip():
            continue
        if str(getattr(item, 'type', '') or '') == 'openai_compat' and not has_image_api_key(session, int(provider_id)):
            continue
        valid.append(item)
    if default_id <= 0:
        return valid
    valid.sort(key=lambda item: (0 if int(getattr(item, 'id', 0) or 0) == default_id else 1, int(getattr(item, 'id', 0) or 0)))
    return valid


def set_default_image_provider(session, provider_id: int) -> None:
    items = session.exec(select(ImageProvider)).all()
    for p in items:
        p.is_default = bool(p.id == provider_id)
        p.updated_at = now_utc()
        session.add(p)


def normalize_image_providers(session) -> None:
    rows = session.exec(select(ImageProvider).order_by(ImageProvider.id)).all()
    if not rows:
        return
    keeper = next((item for item in rows if bool(getattr(item, "is_default", False))), rows[-1])
    keep_default = bool(getattr(keeper, "is_default", False)) or any(bool(getattr(item, "is_default", False)) for item in rows)
    for item in rows:
        if item is keeper:
            continue
        if item.id is not None:
            for secret in session.exec(select(ImageSecret).where(ImageSecret.provider_id == int(item.id))).all():
                secret.provider_id = int(keeper.id or item.id)
                secret.updated_at = now_utc()
                session.add(secret)
            session.delete(item)
    if keep_default and not bool(getattr(keeper, "is_default", False)):
        keeper.is_default = True
        keeper.enabled = True
        keeper.updated_at = now_utc()
        session.add(keeper)


def upsert_provider(session, *, name: str, type_: str, base_url: str, default_model: str, enabled: bool, is_default: bool) -> ImageProvider:
    existing = session.exec(select(ImageProvider).where(ImageProvider.is_default == True)).first()  # noqa: E712
    if not existing:
        existing = session.exec(select(ImageProvider).order_by(ImageProvider.id.desc())).first()
    if existing:
        existing.name = name.strip()
        existing.type = type_
        existing.base_url = base_url
        existing.default_model = default_model
        existing.enabled = bool(enabled)
        existing.is_default = bool(is_default)
        existing.updated_at = now_utc()
        session.add(existing)
        return existing
    p = ImageProvider(
        name=name.strip(),
        type=type_,
        base_url=base_url,
        default_model=default_model,
        enabled=bool(enabled),
        is_default=bool(is_default),
    )
    session.add(p)
    session.flush()
    session.refresh(p)
    return p


def upsert_image_api_key(session, provider_id: int, api_key: str) -> None:
    existing = session.exec(
        select(ImageSecret).where(ImageSecret.provider_id == provider_id).where(ImageSecret.name == "api_key")
    ).first()
    enc = encrypt_str((api_key or "").strip())
    if existing:
        existing.value_enc = enc
        existing.updated_at = now_utc()
        session.add(existing)
        return
    session.add(ImageSecret(provider_id=provider_id, name="api_key", value_enc=enc))


def has_image_api_key(session, provider_id: int) -> bool:
    s = session.exec(
        select(ImageSecret).where(ImageSecret.provider_id == provider_id).where(ImageSecret.name == "api_key")
    ).first()
    return bool(s and (s.value_enc or "").strip())


def get_image_api_key(session, provider_id: int) -> str:
    s = session.exec(
        select(ImageSecret).where(ImageSecret.provider_id == provider_id).where(ImageSecret.name == "api_key")
    ).first()
    if not s or not getattr(s, "value_enc", ""):
        return ""
    return decrypt_str(str(getattr(s, "value_enc", "") or ""))
