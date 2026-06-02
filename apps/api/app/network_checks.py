from __future__ import annotations

import requests

from app.proxy_settings import detect_tts_proxy


def tts_proxy_summary() -> dict[str, str | bool]:
    proxy = detect_tts_proxy()
    return {
        "proxy_detected": bool(proxy),
        "proxy": str(proxy or ""),
    }


def https_probe(url: str, *, timeout_s: int = 8) -> tuple[bool, str]:
    try:
        proxy = detect_tts_proxy()
        proxies = {"http": proxy, "https": proxy} if proxy else None
        r = requests.get(url, timeout=timeout_s, proxies=proxies, headers={"User-Agent": "Mozilla/5.0"})
        if r.ok:
            return (True, f"HTTP {r.status_code}")
        return (False, f"HTTP {r.status_code}")
    except Exception as e:
        return (False, str(e)[:220])
