
import time
from dataclasses import dataclass
from pathlib import Path
from app.settings import settings
from app.ffmpeg_utils import ffmpeg_path, run_ffmpeg

from app.app_config_service import get_app_config, set_app_config
from app.modules.tts.offline import OfflineTtsStatus, list_available_offline_voices, offline_piper_audio_only, offline_tts_status
from app.modules.tts.catalog import DEFAULT_VOICE_ID
from app.modules.tts.runtime import edge_tts_audio_only, edge_tts_list_voices, edge_tts_to_files


@dataclass(frozen=True)
class TtsRunResult:
    backend: str
    detail: str = ""


TTS_BACKEND_KEY = "tts.backend"
TTS_OFFLINE_VOICE_KEY = "tts.offline.voice_id"
TTS_EDGE_VOICE_KEY = "tts.edge.voice"
TTS_DEFAULT_RATE_KEY = "tts.default.rate"
DEFAULT_EDGE_VOICE = "zh-CN-XiaoxiaoNeural"
_EDGE_PROBE_CACHE: dict[str, object] = {"checked": False, "ok": False, "detail": "", "checked_at": 0.0}


def normalize_tts_rate(rate: str) -> str:
    text = str(rate or "").strip()
    import re

    match = re.match(r"^([+-]?)(\d+)%$", text)
    if not match:
        return "+0%"
    sign = -1 if match.group(1) == "-" else 1
    value = max(-20, min(40, int(match.group(2)) * sign))
    return f"{value:+d}%"


def _wav_to_mp3(wav: Path, mp3: Path) -> None:
    """Convert WAV to MP3 and clean up source."""
    run_ffmpeg(["-y", "-i", ffmpeg_path(wav), "-c:a", "libmp3lame", "-b:a", "128k", ffmpeg_path(mp3)])
    try:
        wav.unlink(missing_ok=True)
    except Exception:
        pass


def get_tts_backend(session) -> str:
    v = (get_app_config(session, TTS_BACKEND_KEY, "offline_piper") or "offline_piper").strip().lower()
    if v not in ("auto", "edge", "offline_piper"):
        v = "offline_piper"
    return v


def set_tts_backend(session, backend: str) -> str:
    b = (backend or "").strip().lower()
    if b not in ("auto", "edge", "offline_piper"):
        b = "offline_piper"
    set_app_config(session, TTS_BACKEND_KEY, b)
    return b


def get_offline_voice_id(session) -> str:
    v = (get_app_config(session, TTS_OFFLINE_VOICE_KEY, DEFAULT_VOICE_ID) or DEFAULT_VOICE_ID).strip()
    return v or DEFAULT_VOICE_ID


def set_offline_voice_id(session, voice_id: str) -> str:
    v = (voice_id or "").strip() or DEFAULT_VOICE_ID
    set_app_config(session, TTS_OFFLINE_VOICE_KEY, v)
    return v


def get_edge_voice_id(session) -> str:
    v = (get_app_config(session, TTS_EDGE_VOICE_KEY, DEFAULT_EDGE_VOICE) or DEFAULT_EDGE_VOICE).strip()
    return v or DEFAULT_EDGE_VOICE


def set_edge_voice_id(session, voice_id: str) -> str:
    v = (voice_id or "").strip() or DEFAULT_EDGE_VOICE
    set_app_config(session, TTS_EDGE_VOICE_KEY, v)
    return v


def get_default_voice_rate(session) -> str:
    return normalize_tts_rate(get_app_config(session, TTS_DEFAULT_RATE_KEY, "+0%") or "+0%")


def set_default_voice_rate(session, rate: str) -> str:
    value = normalize_tts_rate(rate)
    set_app_config(session, TTS_DEFAULT_RATE_KEY, value)
    return value


def list_available_edge_voices(*, force: bool = False) -> list[dict]:
    rows = edge_tts_list_voices(force=force)
    out: list[dict] = []
    for row in rows:
        short_name = str(row.get("ShortName") or "").strip()
        if not short_name:
            continue
        out.append(
            {
                "voice_id": short_name,
                "label": str(row.get("FriendlyName") or short_name),
                "locale": str(row.get("Locale") or ""),
                "gender": str(row.get("Gender") or ""),
            }
        )
    out.sort(key=lambda item: (0 if item.get("locale") == "zh-CN" else 1, str(item.get("locale") or ""), str(item.get("label") or "")))
    return out


def edge_synthesis_probe(*, voice: str, rate: str, timeout_s: int = 10) -> tuple[bool, str]:
    """Fast probe to decide whether Edge synthesis is usable.

    Returns (ok, detail).
    """

    try:
        out_dir = settings.exports_dir / "tts_previews"
        out_dir.mkdir(parents=True, exist_ok=True)
        tmp = out_dir / "_edge_probe.mp3"
        try:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
        except Exception:
            pass
        edge_tts_audio_only(text="你好", voice=voice, rate=rate, audio_path=tmp, timeout_s=int(timeout_s))
        ok = tmp.exists() and tmp.stat().st_size > 0
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        return (bool(ok), "合成正常" if ok else "合成失败")
    except Exception as e:
        detail = str(e)[:200]
        if "timeout" in detail.lower():
            detail = f"在线探测超时（{int(timeout_s)}s）"
        return (False, detail)


def edge_synthesis_probe_cached(*, voice: str, rate: str, timeout_s: int = 8, ttl_s: int = 180, force: bool = False) -> tuple[bool, str, bool]:
    now = time.time()
    checked = bool(_EDGE_PROBE_CACHE.get("checked"))
    checked_at_raw = _EDGE_PROBE_CACHE.get("checked_at")
    checked_at = 0.0
    if isinstance(checked_at_raw, (int, float)):
        checked_at = float(checked_at_raw)
    if checked and not force and now - checked_at <= max(10, int(ttl_s or 180)):
        return (bool(_EDGE_PROBE_CACHE.get("ok")), str(_EDGE_PROBE_CACHE.get("detail") or ""), True)
    ok, detail = edge_synthesis_probe(voice=voice, rate=rate, timeout_s=int(timeout_s or 8))
    _EDGE_PROBE_CACHE["checked"] = True
    _EDGE_PROBE_CACHE["ok"] = bool(ok)
    _EDGE_PROBE_CACHE["detail"] = str(detail or "")
    _EDGE_PROBE_CACHE["checked_at"] = now
    return (bool(ok), str(detail or ""), True)


def edge_synthesis_cached_state(*, voice: str, rate: str, timeout_s: int = 8, ttl_s: int = 180) -> tuple[bool, bool, str]:
    checked = bool(_EDGE_PROBE_CACHE.get("checked"))
    if not checked:
        return (False, False, "")
    ok, detail, _checked = edge_synthesis_probe_cached(voice=voice, rate=rate, timeout_s=timeout_s, ttl_s=ttl_s, force=False)
    return (bool(_checked), bool(ok), str(detail or ""))


def tts_to_files(
    *,
    session,
    text: str,
    voice: str,
    rate: str,
    audio_path: Path,
    srt_path: Path,
    words_in_cue: int = 8,
    strict: bool = True,
) -> TtsRunResult:
    """Generate audio (mp3) and subtitles (srt) with auto fallback.

    - auto: probe edge quickly; if ok -> edge full; else -> offline.
    - edge: edge only.
    - offline_piper: offline only.
    """

    backend = get_tts_backend(session)
    offline_voice_id = get_offline_voice_id(session)
    text2 = (text or "").strip()
    if not text2:
        raise RuntimeError("TTS 文本为空")

    if backend == "edge":
        edge_tts_to_files(
            text=text2,
            voice=voice,
            rate=rate,
            audio_path=audio_path,
            srt_path=srt_path,
            words_in_cue=words_in_cue,
            timeout_s=180,
        )
        return TtsRunResult(backend="edge", detail="Edge TTS")

    if backend == "offline_piper":
        st = offline_tts_status(voice_id=offline_voice_id, probe=False)
        if not st.installed:
            raise RuntimeError("离线配音未安装：请到 设置->配音 一键安装离线中文配音")
        wav = audio_path.with_suffix(".wav")
        offline_piper_audio_only(text=text2, voice_id=offline_voice_id, wav_path=wav)
        _wav_to_mp3(wav, audio_path)
        return TtsRunResult(backend="offline_piper", detail=f"离线配音（{offline_voice_id}）")

    # auto mode
    probe_ok, probe_detail = edge_synthesis_probe(voice=voice, rate=rate, timeout_s=12)
    if probe_ok:
        try:
            edge_tts_to_files(
                text=text2,
                voice=voice,
                rate=rate,
                audio_path=audio_path,
                srt_path=srt_path,
                words_in_cue=words_in_cue,
                timeout_s=240,
            )
            return TtsRunResult(backend="edge", detail="Edge TTS")
        except Exception as e:
            edge_err = str(e)
    else:
        edge_err = f"Edge probe failed: {probe_detail}"

    st2 = offline_tts_status(voice_id=offline_voice_id, probe=False)
    if not st2.installed:
        msg = "无法生成配音/字幕：Edge TTS 不可用，且离线配音未安装。"
        msg += " 请到 设置->配音 一键安装离线中文配音。"
        msg += f"（{edge_err}）"
        raise RuntimeError(msg)

    wav = audio_path.with_suffix(".wav")
    offline_piper_audio_only(text=text2, voice_id=offline_voice_id, wav_path=wav)
    _wav_to_mp3(wav, audio_path)
    return TtsRunResult(backend="offline_piper", detail=f"离线配音（{offline_voice_id}）")


def tts_status_dict(*, session, probe_edge: bool = False) -> dict:
    backend = get_tts_backend(session)
    offline_voice_id = get_offline_voice_id(session)
    edge_voice_id = get_edge_voice_id(session)
    default_voice_rate = get_default_voice_rate(session)
    off = offline_tts_status(voice_id=offline_voice_id, probe=True)

    # Delegate to tts_smart.py for compatible voice list (avoids duplicating phoneme_type filter logic).
    installed_ids: list[str] = []
    try:
        from app.modules.tts.smart import _installed_offline_voice_ids

        installed_ids = _installed_offline_voice_ids()
    except Exception:
        installed_ids = []

    try:
        available_voices = list_available_offline_voices(force=False)
    except Exception:
        available_voices = []
    try:
        available_edge_voices = list_available_edge_voices(force=False)
    except Exception:
        available_edge_voices = []
    zh_cn_edge_voices = [v for v in available_edge_voices if str(v.get("locale") or "") == "zh-CN"]

    edge_checked = bool(_EDGE_PROBE_CACHE.get("checked"))
    edge_ok = bool(_EDGE_PROBE_CACHE.get("ok"))
    edge_detail = str(_EDGE_PROBE_CACHE.get("detail") or "")
    if probe_edge:
        edge_ok, edge_detail, edge_checked = edge_synthesis_probe_cached(voice=edge_voice_id, rate="+10%", timeout_s=8, force=True)
    elif edge_checked:
        edge_ok, edge_detail, edge_checked = edge_synthesis_probe_cached(voice=edge_voice_id, rate="+10%", timeout_s=8, force=False)
    else:
        edge_ok = False
        edge_detail = "未检测（需要时可手动刷新）"
    return {
        "backend": backend,
        "offline_voice_id": offline_voice_id,
        "edge_voice_id": edge_voice_id,
        "default_voice_rate": default_voice_rate,
        "edge_synthesis_ok": bool(edge_ok),
        "edge_checked": bool(edge_checked),
        "edge_detail": edge_detail,
        "offline_installed": bool(off.installed),
        "offline_ok": bool(off.ok),
        "offline_detail": off.detail,
        "offline_installed_voice_ids": installed_ids,
        "offline_installed_voice_count": len(installed_ids),
        "available_offline_voice_ids": [str(v.get("voice_id") or "") for v in available_voices if str(v.get("voice_id") or "").strip()],
        "available_offline_voice_count": len(available_voices),
        "available_offline_voices": available_voices,
        "available_edge_voice_ids": [str(v.get("voice_id") or "") for v in available_edge_voices if str(v.get("voice_id") or "").strip()],
        "available_edge_voice_count": len(available_edge_voices),
        "available_edge_voices": available_edge_voices,
        "available_edge_zh_cn_voice_count": len(zh_cn_edge_voices),
    }
