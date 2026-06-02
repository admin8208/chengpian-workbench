from __future__ import annotations

import hmac
import base64
import json
import os
import time
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote

from app.project_paths import project_path_from_rel, projects_root_dir
from app.settings import settings


def _secret_key() -> str:
    value = (os.environ.get('CHENGPIAN_FILE_TOKEN_SECRET', '') or '').strip()
    if value:
        return value
    return f'{settings.database_url}|{settings.data_dir}'


def _sign(payload: str) -> str:
    return hmac.new(_secret_key().encode('utf-8'), payload.encode('utf-8'), sha256).hexdigest()


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def _b64decode(value: str) -> bytes:
    pad = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode(f'{value}{pad}'.encode('ascii'))


def sign_file_token(scope: str, rel_path: str, *, ttl_seconds: int = 86400) -> str:
    normalized = str(rel_path or '').lstrip('/')
    payload = {
        'scope': str(scope or ''),
        'path': normalized,
        'exp': int(time.time()) + max(60, int(ttl_seconds or 86400)),
    }
    payload_raw = json.dumps(payload, separators=(',', ':'), ensure_ascii=True).encode('utf-8')
    payload_b64 = _b64encode(payload_raw)
    return f'{payload_b64}.{_sign(payload_b64)}'


def signed_file_url(scope: str, rel_path: str) -> str:
    normalized = str(rel_path or '').lstrip('/')
    token = sign_file_token(scope, normalized)
    return f'/api/files/s/{scope}/{quote(normalized)}?token={token}'


def verify_file_token(scope: str, rel_path: str, token: str) -> bool:
    raw = str(token or '').strip()
    if not raw or '.' not in raw:
        return False
    payload_b64, sig = raw.split('.', 1)
    if not hmac.compare_digest(_sign(payload_b64), sig):
        return False
    try:
        payload = json.loads(_b64decode(payload_b64).decode('utf-8'))
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False
    try:
        exp = int(payload.get('exp') or 0)
    except Exception:
        return False
    normalized = str(rel_path or '').lstrip('/')
    return exp > int(time.time()) and payload.get('scope') == scope and payload.get('path') == normalized


def resolve_scoped_file(scope: str, rel_path: str) -> Path:
    normalized = str(rel_path or '').lstrip('/')
    if scope == 'assets':
        base = settings.assets_dir.resolve()
        path = (base / normalized).resolve()
    elif scope == 'exports':
        base = settings.exports_dir.resolve()
        path = (base / normalized).resolve()
    elif scope == 'tools':
        base = (settings.data_dir / 'tools').resolve()
        path = (base / normalized).resolve()
    elif scope == 'projects':
        base = projects_root_dir().resolve()
        path = project_path_from_rel(normalized).resolve()
    else:
        raise RuntimeError('unsupported file scope')
    if path != base and base not in path.parents:
        raise RuntimeError('invalid file path')
    return path
