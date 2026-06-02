import os
import subprocess
from functools import lru_cache


def _normalize_proxy_url(value: str) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    if s.startswith(("http://", "https://", "socks5://", "socks5h://")):
        return s
    return f"http://{s}"


def _parse_windows_proxy_server(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    # Windows may return: http=127.0.0.1:7890;https=127.0.0.1:7890
    if "=" in s:
        parts = [x.strip() for x in s.split(";") if x.strip()]
        mapping: dict[str, str] = {}
        for part in parts:
            if "=" not in part:
                continue
            k, v = part.split("=", 1)
            mapping[k.strip().lower()] = v.strip()
        for key in ("https", "http", "socks", "socks5"):
            if mapping.get(key):
                val = mapping[key]
                if key in ("socks", "socks5") and not val.startswith("socks5"):
                    return f"socks5://{val}"
                return _normalize_proxy_url(val)
    return _normalize_proxy_url(s)


def _read_winhttp_proxy() -> str:
    if os.name != "nt":
        return ""
    try:
        p = subprocess.run(
            ["netsh", "winhttp", "show", "proxy"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=4,
            check=False,
        )
        txt = (p.stdout or "") + "\n" + (p.stderr or "")
        for line in txt.splitlines():
            low = line.lower()
            if "proxy server" in low or "代理服务器" in low:
                if ":" in line:
                    return _parse_windows_proxy_server(line.split(":", 1)[1])
        return ""
    except Exception:
        return ""


def _read_windows_user_proxy() -> str:
    if os.name != "nt":
        return ""
    try:
        import winreg

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        enabled = int(winreg.QueryValueEx(key, "ProxyEnable")[0] or 0)
        if not enabled:
            return ""
        server = str(winreg.QueryValueEx(key, "ProxyServer")[0] or "")
        return _parse_windows_proxy_server(server)
    except Exception:
        return ""


@lru_cache(maxsize=1)
def detect_tts_proxy() -> str:
    val = _normalize_proxy_url(os.environ.get("CHENGPIAN_TTS_PROXY", ""))
    if val:
        return val
    winhttp = _read_winhttp_proxy()
    if winhttp:
        return winhttp
    user_proxy = _read_windows_user_proxy()
    if user_proxy:
        return user_proxy
    return ""


def tts_proxy_env() -> dict[str, str]:
    proxy = detect_tts_proxy()
    if not proxy:
        return {}
    return {
        "HTTPS_PROXY": proxy,
        "https_proxy": proxy,
        "HTTP_PROXY": proxy,
        "http_proxy": proxy,
    }
