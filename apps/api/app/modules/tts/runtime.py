
import asyncio
from contextlib import contextmanager
from pathlib import Path
import os
import multiprocessing
import re
import threading

import edge_tts

from app.subtitles import clean_tts_text, naive_srt_from_lines, vtt_to_srt
from app.proxy_settings import detect_tts_proxy, tts_proxy_env


def _detect_installed_edge_version() -> str:
    if os.name != "nt":
        return ""
    roots = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application"),
        Path(r"C:\Program Files\Microsoft\Edge\Application"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "Application",
    ]
    versions: list[tuple[int, int, int, int]] = []
    raw_map: dict[tuple[int, int, int, int], str] = {}
    for root in roots:
        if not root.exists():
            continue
        for child in root.iterdir():
            if not child.is_dir():
                continue
            m = re.match(r"^(\d+)\.(\d+)\.(\d+)\.(\d+)$", child.name)
            if not m:
                continue
            key = tuple(int(x) for x in m.groups())
            versions.append(key)
            raw_map[key] = child.name
    if not versions:
        return ""
    versions.sort(reverse=True)
    return raw_map.get(versions[0], "")


def _sync_edge_tts_runtime() -> None:
    try:
        version = _detect_installed_edge_version().strip()
        if not version:
            return
        major = version.split(".", 1)[0]
        import edge_tts.constants as c
        import edge_tts.communicate as comm
        import edge_tts.voices as voices

        c.CHROMIUM_FULL_VERSION = version
        c.CHROMIUM_MAJOR_VERSION = major
        c.SEC_MS_GEC_VERSION = f"1-{version}"
        c.BASE_HEADERS.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    f"(KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36 Edg/{major}.0.0.0"
                )
            }
        )
        c.WSS_HEADERS.update(c.BASE_HEADERS)
        c.VOICE_HEADERS.update(c.BASE_HEADERS)
        c.VOICE_HEADERS.update(
            {
                "Sec-CH-UA": f'" Not;A Brand";v="99", "Microsoft Edge";v="{major}", "Chromium";v="{major}"',
            }
        )

        comm.SEC_MS_GEC_VERSION = c.SEC_MS_GEC_VERSION
        comm.WSS_HEADERS = c.WSS_HEADERS
        voices.SEC_MS_GEC_VERSION = c.SEC_MS_GEC_VERSION
        voices.VOICE_HEADERS = c.VOICE_HEADERS
    except Exception:
        pass


_sync_edge_tts_runtime()

_EDGE_VOICE_CACHE: dict[str, object] = {"checked_at": 0.0, "voices": []}


@contextmanager
def _temporary_tts_proxy_env():
    env = tts_proxy_env()
    if not env:
        yield
        return
    old = {key: os.environ.get(key) for key in env}
    try:
        os.environ.update(env)
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        result: dict[str, object] = {}
        error: dict[str, BaseException] = {}

        def _runner() -> None:
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                result["value"] = loop.run_until_complete(coro)
            except BaseException as exc:
                error["value"] = exc
            finally:
                try:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception:
                    pass
                asyncio.set_event_loop(None)
                loop.close()

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join()
        if "value" in error:
            raise error["value"]
        return result.get("value")


def edge_tts_list_voices(*, ttl_s: int = 3600, force: bool = False) -> list[dict]:
    import time
    import edge_tts.voices as voices

    checked_at = float(_EDGE_VOICE_CACHE.get("checked_at") or 0.0)
    cached = _EDGE_VOICE_CACHE.get("voices")
    if isinstance(cached, list) and cached and not force and time.time() - checked_at <= max(60, int(ttl_s or 3600)):
        return [dict(v) for v in cached if isinstance(v, dict)]

    proxy = detect_tts_proxy() or None
    with _temporary_tts_proxy_env():
        raw = _run_async(voices.list_voices(proxy=proxy))
    items = [dict(v) for v in (raw or []) if isinstance(v, dict)]
    _EDGE_VOICE_CACHE["voices"] = items
    _EDGE_VOICE_CACHE["checked_at"] = time.time()
    return [dict(v) for v in items]


def _estimate_tts_duration(text: str, rate: str) -> float:
    txt = str(text or "").strip()
    if not txt:
        return 1.0
    units = max(1, len([c for c in txt if not c.isspace()]))
    base = max(2.0, units / 5.2)
    try:
        s = str(rate or "").strip()
        sign = -1 if s.startswith("-") else 1
        pct = int("".join(ch for ch in s if ch.isdigit()) or "0") * sign
    except Exception:
        pct = 0
    speed = max(0.72, min(1.45, 1.0 + (pct / 100.0)))
    return max(1.8, base / speed)


def _edge_tts_to_files_impl(
    *,
    text: str,
    voice: str,
    rate: str,
    audio_path: Path,
    srt_path: Path,
    words_in_cue: int,
) -> None:
    proxy = detect_tts_proxy() or None
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    srt_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp first to avoid leaving 0-byte files on crash/kill.
    audio_tmp = audio_path.with_suffix(audio_path.suffix + ".tmp")
    srt_tmp = srt_path.with_suffix(srt_path.suffix + ".tmp")
    if audio_tmp.exists():
        try:
            audio_tmp.unlink()
        except Exception:
            pass
    if srt_tmp.exists():
        try:
            srt_tmp.unlink()
        except Exception:
            pass

    text = clean_tts_text(text)
    tts = edge_tts.Communicate(text=text, voice=voice, rate=rate, proxy=proxy)
    subs = edge_tts.SubMaker()
    word_boundary_count = 0

    with open(audio_tmp, "wb") as audio_file:
        for chunk in tts.stream_sync():
            if chunk.get("type") == "audio":
                audio_file.write(chunk["data"])
            elif chunk.get("type") == "WordBoundary":
                subs.create_sub((chunk["offset"], chunk["duration"]), chunk["text"])
                word_boundary_count += 1

    # Enhanced fallback: if WordBoundary info is missing or insufficient, use estimation
    if word_boundary_count == 0:
        # Estimate audio duration based on text length and speech rate
        estimated_duration = _estimate_tts_duration(text, rate)
        srt_content = naive_srt_from_lines(text, total_duration=estimated_duration)
        srt_tmp.write_text(srt_content, encoding="utf-8")
    else:
        vtt = subs.generate_subs(words_in_cue=words_in_cue)
        srt = vtt_to_srt(vtt)
        
        # Validate subtitle coverage
        text_chars = len([c for c in text if not c.isspace()])
        srt_chars = len([c for c in srt if not c.isspace()])
        coverage_ratio = srt_chars / max(1, text_chars) if text_chars > 0 else 0.0
        
        # If subtitle coverage is too low, try to repair
        if coverage_ratio < 0.8:
            # Use fallback method to ensure subtitle completeness
            estimated_duration = _estimate_tts_duration(text, rate)
            fallback_srt = naive_srt_from_lines(text, total_duration=estimated_duration)
            if len(fallback_srt) > len(srt):
                srt_tmp.write_text(fallback_srt, encoding="utf-8")
            else:
                srt_tmp.write_text(srt, encoding="utf-8")
        else:
            srt_tmp.write_text(srt, encoding="utf-8")

    # Atomic-ish replace.
    audio_tmp.replace(audio_path)
    srt_tmp.replace(srt_path)


def _edge_tts_audio_only_impl(*, text: str, voice: str, rate: str, audio_path: Path) -> None:
    proxy = detect_tts_proxy() or None
    text = clean_tts_text(text)
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_tmp = audio_path.with_suffix(audio_path.suffix + ".tmp")
    if audio_tmp.exists():
        try:
            audio_tmp.unlink()
        except Exception:
            pass
    tts = edge_tts.Communicate(text=text, voice=voice, rate=rate, proxy=proxy)
    with open(audio_tmp, "wb") as audio_file:
        for chunk in tts.stream_sync():
            if chunk.get("type") == "audio":
                audio_file.write(chunk["data"])
    audio_tmp.replace(audio_path)


def _edge_tts_ssml_impl(
    *,
    text: str,
    voice: str,
    ssml_rate: str | None = None,
    ssml_pitch: str | None = None,
    ssml_volume: str | None = None,
    audio_path: Path,
) -> None:
    """Generate audio with SSML markup for precise control.
    
    Args:
        text: Raw text or SSML markup (will be wrapped in <speak> if not already)
        voice: Edge TTS voice name
        ssml_rate: Prosody rate e.g. "+20%", "-10%"
        ssml_pitch: Prosody pitch e.g. "+2st", "-1st"
        ssml_volume: Prosody volume e.g. "+10%", "-5%"
        audio_path: Output path
    """
    proxy = detect_tts_proxy() or None
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_tmp = audio_path.with_suffix(audio_path.suffix + ".tmp")
    if audio_tmp.exists():
        try:
            audio_tmp.unlink()
        except Exception:
            pass
    
    # Build SSML with prosody control
    ssml_text = clean_tts_text(text)
    
    # If not already SSML, wrap in <speak> and add prosody
    if not ssml_text.startswith("<"):
        parts = []
        # Add prosody tags around the text
        prosody_attrs = []
        if ssml_rate:
            prosody_attrs.append(f'rate="{ssml_rate}"')
        if ssml_pitch:
            prosody_attrs.append(f'pitch="{ssml_pitch}"')
        if ssml_volume:
            prosody_attrs.append(f'volume="{ssml_volume}"')
        
        if prosody_attrs:
            prosody_tag = "<prosody " + " ".join(prosody_attrs) + ">"
            ssml_text = f"<speak>{prosody_tag}{ssml_text}</prosody></speak>"
        else:
            ssml_text = f"<speak>{ssml_text}</speak>"
    
    tts = edge_tts.Communicate(text=ssml_text, voice=voice, rate="+0%", proxy=proxy)  # Rate handled in SSML
    with open(audio_tmp, "wb") as audio_file:
        for chunk in tts.stream_sync():
            if chunk.get("type") == "audio":
                audio_file.write(chunk["data"])
    audio_tmp.replace(audio_path)


def _edge_tts_worker(
    q,
    *,
    mode: str,
    text: str,
    voice: str,
    rate: str,
    audio_path: str,
    srt_path: str,
    words_in_cue: int,
    ssml_rate: str | None = None,
    ssml_pitch: str | None = None,
    ssml_volume: str | None = None,
) -> None:
    """Child-process worker for edge-tts.

    Must be a top-level function to be spawn-picklable on Windows.
    """

    try:
        ap = Path(audio_path)
        sp = Path(srt_path)
        m = (mode or "").strip().lower()
        if m == "files":
            _edge_tts_to_files_impl(text=text, voice=voice, rate=rate, audio_path=ap, srt_path=sp, words_in_cue=int(words_in_cue))
        elif m == "audio":
            _edge_tts_audio_only_impl(text=text, voice=voice, rate=rate, audio_path=ap)
        elif m == "ssml":
            _edge_tts_ssml_impl(text=text, voice=voice, ssml_rate=ssml_rate, ssml_pitch=ssml_pitch, ssml_volume=ssml_volume, audio_path=ap)
        else:
            raise RuntimeError(f"unknown edge-tts mode: {mode}")
        q.put((True, ""))
    except Exception as e:
        try:
            q.put((False, str(e)))
        except Exception:
            pass


def _run_edge_tts_with_timeout(
    *,
    mode: str,
    text: str,
    voice: str,
    rate: str,
    audio_path: Path,
    srt_path: Path,
    words_in_cue: int,
    timeout_s: int,
    ssml_rate: str | None = None,
    ssml_pitch: str | None = None,
    ssml_volume: str | None = None,
) -> None:
    """Run edge-tts in a child process with timeout.

    This prevents edge_tts from hanging forever in restricted networks.
    """

    start_method = "spawn" if os.name == "nt" else "fork"
    ctx = multiprocessing.get_context(start_method)
    q: multiprocessing.Queue = ctx.Queue()

    p = ctx.Process(
        target=_edge_tts_worker,
        kwargs={
            "q": q,
            "mode": mode,
            "text": text,
            "voice": voice,
            "rate": rate,
            "audio_path": str(audio_path),
            "srt_path": str(srt_path),
            "words_in_cue": int(words_in_cue),
            "ssml_rate": ssml_rate,
            "ssml_pitch": ssml_pitch,
            "ssml_volume": ssml_volume,
        },
        daemon=True,
    )
    p.start()
    p.join(timeout_s)
    if p.is_alive():
        try:
            p.terminate()
        except Exception:
            pass
        raise TimeoutError(f"edge-tts timeout after {timeout_s}s")

    ok = False
    err = ""
    try:
        ok, err = q.get_nowait()
    except Exception:
        ok, err = (False, "edge-tts failed")
    if not ok:
        raise RuntimeError(err or "edge-tts failed")


def edge_tts_to_files(
    *,
    text: str,
    voice: str,
    rate: str,
    audio_path: Path,
    srt_path: Path,
    words_in_cue: int = 8,
    timeout_s: int | None = None,
) -> None:
    if timeout_s is None:
        timeout_s = int(os.environ.get("CHENGPIAN_TTS_TIMEOUT_S", "120") or "120")

    _run_edge_tts_with_timeout(
        mode="files",
        text=text,
        voice=voice,
        rate=rate,
        audio_path=audio_path,
        srt_path=srt_path,
        words_in_cue=words_in_cue,
        timeout_s=int(timeout_s),
    )


def edge_tts_audio_only(*, text: str, voice: str, rate: str, audio_path: Path, timeout_s: int | None = None) -> None:
    if timeout_s is None:
        timeout_s = int(os.environ.get("CHENGPIAN_TTS_TIMEOUT_S", "120") or "120")

    _run_edge_tts_with_timeout(
        mode="audio",
        text=text,
        voice=voice,
        rate=rate,
        audio_path=audio_path,
        srt_path=audio_path.with_suffix(".srt"),
        words_in_cue=8,
        timeout_s=int(timeout_s),
    )


def edge_tts_ssml(
    *,
    text: str,
    voice: str,
    ssml_rate: str | None = None,
    ssml_pitch: str | None = None,
    ssml_volume: str | None = None,
    audio_path: Path,
    timeout_s: int | None = None,
) -> None:
    """Generate audio using SSML markup for precise prosody control.
    
    This enables:
    - Precise rate control via <prosody rate="...">
    - Precise pitch control via <prosody pitch="...">
    - Volume control via <prosody volume="...">
    - Word-level emphasis via <emphasis>
    - Precise pauses via <break time="...">
    
    Note: Piper offline TTS does not support SSML and will fallback to plain text.
    
    Args:
        text: Text content (plain or SSML markup)
        voice: Edge TTS voice name
        ssml_rate: Rate adjustment, e.g. "+20%", "-10%"
        ssml_pitch: Pitch adjustment, e.g. "+2st", "-1st"  
        ssml_volume: Volume adjustment, e.g. "+10%", "-5%"
        audio_path: Output audio path
        timeout_s: Timeout in seconds
    """
    if timeout_s is None:
        timeout_s = int(os.environ.get("CHENGPIAN_TTS_TIMEOUT_S", "120") or "120")

    _run_edge_tts_with_timeout(
        mode="ssml",
        text=text,
        voice=voice,
        rate="+0%",  # Rate handled via SSML prosody
        audio_path=audio_path,
        srt_path=audio_path.with_suffix(".srt"),
        words_in_cue=8,
        timeout_s=int(timeout_s),
        ssml_rate=ssml_rate,
        ssml_pitch=ssml_pitch,
        ssml_volume=ssml_volume,
    )
