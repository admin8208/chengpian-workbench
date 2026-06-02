from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path

from fastapi import HTTPException, Request
from sqlmodel import select

from app.models import AppConfig, UserAccount
from app.settings import settings
from app.time_utils import now_utc


AUTH_COOKIE_NAME = "chengpian_session"
AUTH_COOKIE_MAX_AGE = 60 * 60 * 24 * 7
AUTH_SETUP_PATHS = {
    "/api/auth/status",
    "/api/auth/setup",
    "/api/auth/login",
    "/api/auth/logout",
}


def _session_secret_path() -> Path:
    return settings.data_dir / "auth_session.key"


def _session_secret() -> bytes:
    p = _session_secret_path()
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(secrets.token_bytes(32))
    return p.read_bytes()


def _get_config(session, key: str) -> str:
    row = session.exec(select(AppConfig).where(AppConfig.key == key)).first()
    return str(getattr(row, "value", "") or "")


def _set_config(session, key: str, value: str) -> None:
    row = session.exec(select(AppConfig).where(AppConfig.key == key)).first()
    if row:
        row.value = value
        session.add(row)
        return
    session.add(AppConfig(key=key, value=value))


def auth_is_configured(session) -> bool:
    username = _get_config(session, "auth.admin.username").strip()
    password_hash = _get_config(session, "auth.admin.password_hash").strip()
    salt = _get_config(session, "auth.admin.password_salt").strip()
    return bool(username and password_hash and salt)


def current_admin_username(session) -> str:
    return _get_config(session, "auth.admin.username").strip()


def _normalize_username(username: str) -> str:
    return str(username or "").strip()


def _hash_password(password: str, salt: str) -> str:
    raw = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt.encode("utf-8"), 200_000)
    return base64.b64encode(raw).decode("ascii")


def set_admin_credentials(session, *, username: str, password: str) -> str:
    u = _normalize_username(username)
    p = str(password or "")
    if len(u) < 3:
        raise HTTPException(status_code=400, detail="用户名至少 3 个字符")
    if len(p) < 8:
        raise HTTPException(status_code=400, detail="密码至少 8 个字符")
    salt = secrets.token_urlsafe(16)
    password_hash = _hash_password(p, salt)
    _set_config(session, "auth.admin.username", u)
    _set_config(session, "auth.admin.password_salt", salt)
    _set_config(session, "auth.admin.password_hash", password_hash)
    return u


def verify_login(session, *, username: str, password: str) -> bool:
    expected_username = current_admin_username(session)
    salt = _get_config(session, "auth.admin.password_salt")
    expected_hash = _get_config(session, "auth.admin.password_hash")
    if not expected_username or not salt or not expected_hash:
        return False
    if not hmac.compare_digest(expected_username, str(username or "").strip()):
        return False
    actual_hash = _hash_password(password, salt)
    return hmac.compare_digest(expected_hash, actual_hash)


def get_user_account_by_username(session, username: str) -> UserAccount | None:
    u = _normalize_username(username)
    if not u:
        return None
    return session.exec(select(UserAccount).where(UserAccount.username == u)).first()


def list_user_accounts(session) -> list[UserAccount]:
    items = session.exec(select(UserAccount)).all()
    return sorted(items, key=lambda item: (item.created_at, int(item.id or 0)), reverse=True)


def create_user_account(session, *, username: str, password: str) -> UserAccount:
    u = _normalize_username(username)
    p = str(password or "")
    if len(u) < 3:
        raise HTTPException(status_code=400, detail="用户名至少 3 个字符")
    if len(p) < 8:
        raise HTTPException(status_code=400, detail="密码至少 8 个字符")
    if u == current_admin_username(session):
        raise HTTPException(status_code=400, detail="该用户名已被管理员账号占用")
    existing = get_user_account_by_username(session, u)
    if existing:
        raise HTTPException(status_code=409, detail="子账号用户名已存在")
    salt = secrets.token_urlsafe(16)
    item = UserAccount(username=u, password_salt=salt, password_hash=_hash_password(p, salt), enabled=True)
    session.add(item)
    session.flush()
    session.refresh(item)
    return item


def set_user_account_enabled(session, user_id: int, enabled: bool) -> UserAccount:
    item = session.exec(select(UserAccount).where(UserAccount.id == user_id)).first()
    if not item:
        raise HTTPException(status_code=404, detail="子账号不存在")
    item.enabled = bool(enabled)
    item.updated_at = now_utc()
    session.add(item)
    session.flush()
    session.refresh(item)
    return item


def set_user_account_password(session, user_id: int, password: str) -> UserAccount:
    item = session.exec(select(UserAccount).where(UserAccount.id == user_id)).first()
    if not item:
        raise HTTPException(status_code=404, detail="子账号不存在")
    p = str(password or "")
    if len(p) < 8:
        raise HTTPException(status_code=400, detail="密码至少 8 个字符")
    salt = secrets.token_urlsafe(16)
    item.password_salt = salt
    item.password_hash = _hash_password(p, salt)
    item.updated_at = now_utc()
    session.add(item)
    session.flush()
    session.refresh(item)
    return item


def verify_user_login(session, *, username: str, password: str) -> UserAccount | None:
    item = get_user_account_by_username(session, username)
    if not item or not item.enabled:
        return None
    actual_hash = _hash_password(password, item.password_salt)
    if not hmac.compare_digest(item.password_hash, actual_hash):
        return None
    return item


def authenticate_login(session, *, username: str, password: str) -> dict | None:
    u = _normalize_username(username)
    if verify_login(session, username=u, password=password):
        return {"username": u, "role": "admin", "is_admin": True, "user_id": None}
    item = verify_user_login(session, username=u, password=password)
    if not item or item.id is None:
        return None
    return {"username": item.username, "role": "member", "is_admin": False, "user_id": int(item.id)}


def _sign_payload(payload: bytes) -> str:
    sig = hmac.new(_session_secret(), payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")


def create_session_token(*, username: str, role: str = "admin", user_id: int | None = None) -> str:
    payload = {
        "sub": _normalize_username(username),
        "role": (str(role or "admin").strip().lower() or "admin"),
        "exp": int(time.time()) + AUTH_COOKIE_MAX_AGE,
    }
    if user_id is not None:
        payload["uid"] = int(user_id)
    payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")
    sig_b64 = _sign_payload(payload_bytes)
    return f"{payload_b64}.{sig_b64}"


def _decode_b64url(value: str) -> bytes:
    pad = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{pad}".encode("ascii"))


def verify_session_token(token: str) -> dict | None:
    raw = str(token or "").strip()
    if not raw or "." not in raw:
        return None
    payload_b64, sig_b64 = raw.split(".", 1)
    try:
        payload_bytes = _decode_b64url(payload_b64)
    except Exception:
        return None
    if not hmac.compare_digest(sig_b64, _sign_payload(payload_bytes)):
        return None
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    try:
        exp = int(payload.get("exp") or 0)
    except Exception:
        return None
    if exp <= int(time.time()):
        return None
    sub = str(payload.get("sub") or "").strip()
    if not sub:
        return None
    role = str(payload.get("role") or "admin").strip().lower() or "admin"
    uid_raw = payload.get("uid")
    try:
        user_id = int(uid_raw) if uid_raw is not None else None
    except Exception:
        user_id = None
    return {"username": sub, "exp": exp, "role": role, "user_id": user_id}


def get_authenticated_username(request: Request) -> str | None:
    token = request.cookies.get(AUTH_COOKIE_NAME, "")
    payload = verify_session_token(token)
    return str(payload.get("username") or payload.get("sub") or "") if payload else None


def get_authenticated_principal(request: Request, session) -> dict | None:
    token = request.cookies.get(AUTH_COOKIE_NAME, "")
    payload = verify_session_token(token)
    if not payload:
        return None
    username = _normalize_username(payload.get("username") or payload.get("sub") or "")
    role = str(payload.get("role") or "admin").strip().lower() or "admin"
    if role == "admin":
        current = current_admin_username(session)
        if not current or username != current:
            return None
        return {"username": username, "role": "admin", "is_admin": True, "user_id": None}
    user_id = payload.get("user_id")
    item = session.exec(select(UserAccount).where(UserAccount.id == user_id)).first() if user_id is not None else None
    if not item or item.id is None or not item.enabled or item.username != username:
        return None
    return {"username": item.username, "role": "member", "is_admin": False, "user_id": int(item.id)}


def get_authenticated_admin_username(request: Request, session) -> str | None:
    principal = get_authenticated_principal(request, session)
    if not principal or not principal.get("is_admin"):
        return None
    return str(principal.get("username") or "") or None


def request_is_authenticated(request: Request) -> bool:
    return bool(get_authenticated_username(request))
