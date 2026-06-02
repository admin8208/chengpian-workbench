
"""Small helpers for reading/writing AppConfig.

This is a single-user local app; AppConfig is used for non-secret global toggles.
"""

from sqlmodel import select

from app.models import AppConfig


def get_app_config(session, key: str, default: str = "") -> str:
    k = (key or "").strip()
    if not k:
        return default
    item = session.exec(select(AppConfig).where(AppConfig.key == k)).first()
    if not item:
        return default
    return str(item.value or "")


def set_app_config(session, key: str, value: str) -> None:
    k = (key or "").strip()
    if not k:
        return
    v = str(value or "")
    item = session.exec(select(AppConfig).where(AppConfig.key == k)).first()
    if not item:
        item = AppConfig(key=k, value=v)
        session.add(item)
    else:
        item.value = v
        session.add(item)
