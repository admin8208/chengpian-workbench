
import os
from pathlib import Path

from cryptography.fernet import Fernet

from app.settings import settings


def _key_path() -> Path:
    # Keep it alongside the sqlite db, single-user local security.
    return settings.data_dir / "secret.key"


def get_fernet() -> Fernet:
    p = _key_path()
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(Fernet.generate_key())
    return Fernet(p.read_bytes())


def encrypt_str(value: str) -> str:
    if value is None:
        value = ""
    f = get_fernet()
    token = f.encrypt(value.encode("utf-8"))
    return token.decode("ascii")


def decrypt_str(token: str) -> str:
    if not token:
        return ""
    f = get_fernet()
    raw = f.decrypt(token.encode("ascii"))
    return raw.decode("utf-8")
