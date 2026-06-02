
import os
from typing import Optional

import requests


_DEFAULT_UA = (
    os.environ.get("CHENGPIAN_OFFICIAL_USER_AGENT", "").strip()
    or "ChengpianWorkbench/0.1 (+https://chengpian.local; contact: support@chengpian.local)"
)


def user_agent() -> str:
    # Allow override for deployments/admins, but keep a safe default so end users
    # never need to configure anything.
    ua = os.environ.get("CHENGPIAN_USER_AGENT", "").strip()
    return ua or _DEFAULT_UA


def new_session(*, headers: Optional[dict[str, str]] = None) -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    base_headers = {
        "User-Agent": user_agent(),
        "Accept": "application/json, */*",
    }
    if headers:
        base_headers.update({k: v for k, v in headers.items() if v is not None})
    s.headers.update(base_headers)
    return s
