
"""Catalog for offline TTS assets.

We deliberately do NOT bundle large binaries/models inside the repo.
Instead, we provide reproducible download URLs + local install paths.

Notes:
- Piper binaries come from rhasspy/piper releases.
- Voice models come from rhasspy/piper-voices. In many CN networks,
  huggingface.co may be blocked, so we use hf-mirror.com first.

"""

import json
import time
from dataclasses import dataclass
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class PiperPlatformAsset:
    name: str
    url: str


@dataclass(frozen=True)
class PiperVoice:
    voice_id: str
    label: str
    quality: str
    sample_rate: int
    model_url_primary: str
    model_url_fallback: str
    config_url_primary: str
    config_url_fallback: str


PIPER_RELEASE_TAG = "2023.11.14-2"


PIPER_BINARIES: dict[str, PiperPlatformAsset] = {
    # Windows x64
    "win32_amd64": PiperPlatformAsset(
        name="piper_windows_amd64.zip",
        url=f"https://github.com/rhasspy/piper/releases/download/{PIPER_RELEASE_TAG}/piper_windows_amd64.zip",
    ),
    # Linux x64
    "linux_x86_64": PiperPlatformAsset(
        name="piper_linux_x86_64.tar.gz",
        url=f"https://github.com/rhasspy/piper/releases/download/{PIPER_RELEASE_TAG}/piper_linux_x86_64.tar.gz",
    ),
    # macOS
    "darwin_x64": PiperPlatformAsset(
        name="piper_macos_x64.tar.gz",
        url=f"https://github.com/rhasspy/piper/releases/download/{PIPER_RELEASE_TAG}/piper_macos_x64.tar.gz",
    ),
    "darwin_aarch64": PiperPlatformAsset(
        name="piper_macos_aarch64.tar.gz",
        url=f"https://github.com/rhasspy/piper/releases/download/{PIPER_RELEASE_TAG}/piper_macos_aarch64.tar.gz",
    ),
}


def _hf(primary_path: str) -> tuple[str, str]:
    # Primary: CN-friendly mirror. Fallback: official HuggingFace.
    return (
        f"https://hf-mirror.com/{primary_path}",
        f"https://huggingface.co/{primary_path}",
    )


_base = "rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium"
_m_primary, _m_fallback = _hf(f"{_base}/zh_CN-huayan-medium.onnx")
_c_primary, _c_fallback = _hf(f"{_base}/zh_CN-huayan-medium.onnx.json")


DEFAULT_VOICE_ID = "zh_CN-huayan-medium"

HF_MODEL_ID = "rhasspy/piper-voices"
_HF_TREE_PATH = "zh/zh_CN"
_VOICE_DISCOVERY_CACHE: dict[str, object] = {"checked_at": 0.0, "voice_ids": []}


PIPER_VOICES: dict[str, PiperVoice] = {
    "zh_CN-huayan-medium": PiperVoice(
        voice_id="zh_CN-huayan-medium",
        label="华岩·简体中文（中等质量）",
        quality="medium",
        sample_rate=22050,
        model_url_primary=_m_primary,
        model_url_fallback=_m_fallback,
        config_url_primary=_c_primary,
        config_url_fallback=_c_fallback,
    )
}


def voice_urls_for(voice_id: str) -> PiperVoice:
    vid = (voice_id or "").strip()
    if not vid:
        vid = DEFAULT_VOICE_ID
    if vid in PIPER_VOICES:
        return PIPER_VOICES[vid]

    # Known additional CN voices.
    if vid == "zh_CN-huayan-x_low":
        base = "rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/x_low"
        m1, m2 = _hf(f"{base}/zh_CN-huayan-x_low.onnx")
        c1, c2 = _hf(f"{base}/zh_CN-huayan-x_low.onnx.json")
        return PiperVoice(
            voice_id=vid,
            label="华岩·简体中文（超低质量/更小体积）",
            quality="x_low",
            sample_rate=16000,
            model_url_primary=m1,
            model_url_fallback=m2,
            config_url_primary=c1,
            config_url_fallback=c2,
        )
    if vid == "zh_CN-chaowen-medium":
        base = "rhasspy/piper-voices/resolve/main/zh/zh_CN/chaowen/medium"
        m1, m2 = _hf(f"{base}/zh_CN-chaowen-medium.onnx")
        c1, c2 = _hf(f"{base}/zh_CN-chaowen-medium.onnx.json")
        return PiperVoice(
            voice_id=vid,
            label="超文·简体中文（中等质量）",
            quality="medium",
            sample_rate=22050,
            model_url_primary=m1,
            model_url_fallback=m2,
            config_url_primary=c1,
            config_url_fallback=c2,
        )
    if vid == "zh_CN-xiao_ya-medium":
        base = "rhasspy/piper-voices/resolve/main/zh/zh_CN/xiao_ya/medium"
        m1, m2 = _hf(f"{base}/zh_CN-xiao_ya-medium.onnx")
        c1, c2 = _hf(f"{base}/zh_CN-xiao_ya-medium.onnx.json")
        return PiperVoice(
            voice_id=vid,
            label="小雅·简体中文（中等质量）",
            quality="medium",
            sample_rate=22050,
            model_url_primary=m1,
            model_url_fallback=m2,
            config_url_primary=c1,
            config_url_fallback=c2,
        )

    # Generic zh_CN voice path fallback.
    if vid.startswith("zh_CN-") and vid.count("-") >= 2:
        try:
            rest = vid[len("zh_CN-") :]
            name, quality = rest.rsplit("-", 1)
            base = f"rhasspy/piper-voices/resolve/main/zh/zh_CN/{name}/{quality}"
            m1, m2 = _hf(f"{base}/{vid}.onnx")
            c1, c2 = _hf(f"{base}/{vid}.onnx.json")
            label_name = name.replace("_", " ").strip() or name
            label_name = " ".join(part.capitalize() for part in label_name.split())
            return PiperVoice(
                voice_id=vid,
                label=f"{label_name}·简体中文（{quality}）",
                quality=quality,
                sample_rate=22050,
                model_url_primary=m1,
                model_url_fallback=m2,
                config_url_primary=c1,
                config_url_fallback=c2,
            )
        except Exception:
            pass

    # Fallback to default.
    return PIPER_VOICES[DEFAULT_VOICE_ID]


def known_voice_ids() -> list[str]:
    return [
        "zh_CN-huayan-medium",
        "zh_CN-huayan-x_low",
        "zh_CN-chaowen-medium",
        "zh_CN-xiao_ya-medium",
    ]


def discover_zh_cn_voice_ids(*, force: bool = False, ttl_s: int = 3600) -> list[str]:
    now = time.time()
    if not force and now - float(_VOICE_DISCOVERY_CACHE.get("checked_at") or 0.0) <= max(60, int(ttl_s or 3600)):
        cached = _VOICE_DISCOVERY_CACHE.get("voice_ids") or []
        if isinstance(cached, list) and cached:
            return [str(v) for v in cached if str(v).strip()]

    urls = [
        f"https://huggingface.co/api/models/{HF_MODEL_ID}/tree/main/{_HF_TREE_PATH}?recursive=1",
        f"https://hf-mirror.com/api/models/{HF_MODEL_ID}/tree/main/{_HF_TREE_PATH}?recursive=1",
    ]
    voice_ids: set[str] = set(known_voice_ids())
    for url in urls:
        try:
            req = Request(url, headers={"User-Agent": "chengpian-workbench/1.0"})
            with urlopen(req, timeout=30) as resp:
                rows = json.loads(resp.read().decode("utf-8", errors="ignore") or "[]")
            for row in rows if isinstance(rows, list) else []:
                path = str((row or {}).get("path") or "").strip()
                if not path.endswith(".onnx") or path.endswith(".onnx.json"):
                    continue
                name = path.rsplit("/", 1)[-1].replace(".onnx", "").strip()
                if name.startswith("zh_CN-"):
                    voice_ids.add(name)
            break
        except Exception:
            continue

    out = sorted(voice_ids)
    _VOICE_DISCOVERY_CACHE["checked_at"] = now
    _VOICE_DISCOVERY_CACHE["voice_ids"] = out
    return out
