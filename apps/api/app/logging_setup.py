from __future__ import annotations

import os
import re
import sys
from threading import Lock

from loguru import logger

_CONFIG_LOCK = Lock()
_CONFIGURED = False

_SECRET_PATTERNS = [
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)([^\s,;]+)"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*[\"']?)([^\s\"',;]+)"),
    re.compile(r"(?i)(access[_-]?token\s*[:=]\s*[\"']?)([^\s\"',;]+)"),
    re.compile(r"(?i)(refresh[_-]?token\s*[:=]\s*[\"']?)([^\s\"',;]+)"),
    re.compile(r"(?i)(password\s*[:=]\s*[\"']?)([^\s\"',;]+)"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
]


def sanitize_log_text(value: object) -> str:
    text = str(value or "")
    for pattern in _SECRET_PATTERNS[:-1]:
        text = pattern.sub(lambda match: f"{match.group(1)}***", text)
    text = _SECRET_PATTERNS[-1].sub("sk-***", text)
    return text


def configure_safe_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    with _CONFIG_LOCK:
        if _CONFIGURED:
            return
        level = str(os.environ.get("CHENGPIAN_LOG_LEVEL", "INFO") or "INFO").strip().upper() or "INFO"
        logger.remove()
        logger.add(sys.stderr, level=level, backtrace=False, diagnose=False)
        _CONFIGURED = True
