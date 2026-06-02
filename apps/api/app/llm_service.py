
from sqlmodel import select

from app.models import LlmProvider, Secret
from app.secrets import decrypt_str, encrypt_str
from app.time_utils import now_utc


def get_default_provider(session) -> LlmProvider | None:
    p = session.exec(
        select(LlmProvider).where(LlmProvider.is_default == True)  # noqa: E712
    ).first()
    if p and p.enabled:
        return p
    # fallback: first enabled
    return session.exec(select(LlmProvider).where(LlmProvider.enabled == True).order_by(LlmProvider.id)).first()  # noqa: E712


def set_default_provider(session, provider_id: int) -> None:
    items = session.exec(select(LlmProvider)).all()
    for p in items:
        p.is_default = bool(p.id == provider_id)
        p.updated_at = now_utc()
        session.add(p)


def normalize_llm_providers(session) -> None:
    rows = session.exec(select(LlmProvider).order_by(LlmProvider.id)).all()
    if not rows:
        return
    keeper = next((item for item in rows if bool(getattr(item, "is_default", False))), rows[-1])
    keep_default = bool(getattr(keeper, "is_default", False)) or any(bool(getattr(item, "is_default", False)) for item in rows)
    for item in rows:
        if item is keeper:
            continue
        if item.id is not None:
            for secret in session.exec(select(Secret).where(Secret.provider_id == int(item.id))).all():
                secret.provider_id = int(keeper.id or item.id)
                secret.updated_at = now_utc()
                session.add(secret)
            session.delete(item)
    if keep_default and not bool(getattr(keeper, "is_default", False)):
        keeper.is_default = True
        keeper.enabled = True
        keeper.updated_at = now_utc()
        session.add(keeper)


def upsert_provider(session, *, name: str, type_: str, base_url: str, default_model: str, enabled: bool, is_default: bool) -> LlmProvider:
    existing = session.exec(select(LlmProvider).where(LlmProvider.is_default == True)).first()  # noqa: E712
    if not existing:
        existing = session.exec(select(LlmProvider).order_by(LlmProvider.id.desc())).first()
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
    p = LlmProvider(
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


def upsert_api_key(session, provider_id: int, api_key: str) -> None:
    existing = session.exec(
        select(Secret).where(Secret.provider_id == provider_id).where(Secret.name == "api_key")
    ).first()
    enc = encrypt_str(api_key.strip())
    if existing:
        existing.value_enc = enc
        existing.updated_at = now_utc()
        session.add(existing)
        return
    s = Secret(provider_id=provider_id, name="api_key", value_enc=enc)
    session.add(s)


def has_api_key(session, provider_id: int) -> bool:
    s = session.exec(
        select(Secret).where(Secret.provider_id == provider_id).where(Secret.name == "api_key")
    ).first()
    return bool(s and s.value_enc)


def get_api_key(session, provider_id: int) -> str:
    s = session.exec(
        select(Secret).where(Secret.provider_id == provider_id).where(Secret.name == "api_key")
    ).first()
    if not s or not getattr(s, "value_enc", ""):
        return ""
    return decrypt_str(str(getattr(s, "value_enc", "") or ""))
