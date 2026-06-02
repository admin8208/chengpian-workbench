import hashlib
from loguru import logger
import math
import os
import re
import time
import wave
from contextlib import contextmanager
from pathlib import Path

from app.ffmpeg_utils import ffmpeg_path, run_ffmpeg
from app.modules.tts.offline import offline_piper_audio_only
from app.modules.tts.runtime import edge_tts_audio_only
from app.subtitles import caption_pages, clean_subtitle_display_text, clean_tts_text

from .smart_support import _build_ssml_text


def _hash_key(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update((p or "").encode("utf-8", errors="ignore"))
        h.update(b"\0")
    return h.hexdigest()[:20]


@contextmanager
def _cache_file_lock(target: Path, *, timeout_s: float = 25.0):
    lock = target.with_suffix(target.suffix + ".lock")
    start = time.time()
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, f"pid={os.getpid()} ts={time.time():.3f}".encode("ascii", errors="ignore"))
            finally:
                os.close(fd)
            break
        except FileExistsError:
            if (time.time() - start) >= float(timeout_s):
                try:
                    if lock.exists() and (time.time() - lock.stat().st_mtime) > max(10.0, float(timeout_s)):
                        lock.unlink(missing_ok=True)
                        continue
                except Exception:
                    pass
                raise TimeoutError(f"tts cache lock timeout: {lock.name}")
            time.sleep(0.08)
    try:
        yield
    finally:
        try:
            lock.unlink(missing_ok=True)
        except Exception:
            pass


def _wav_duration_sec(p: Path) -> float:
    try:
        with wave.open(str(p), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate <= 0:
                return 0.0
            return float(frames) / float(rate)
    except Exception:
        return 0.0


def _narrative_rhythm_curve(segment_idx: int, total_segments: int, base_tempo: float, base_rate: str) -> tuple[float, str]:
    if total_segments <= 1:
        return 1.0, "+0%"
    pos = segment_idx / max(1, total_segments - 1)
    if pos < 0.15:
        return 1.06 + (pos / 0.15) * 0.04, "+8%"
    if pos < 0.50:
        t = (pos - 0.15) / 0.35
        return 1.0 + t * 0.10, f"+{int(t * 12)}%"
    if pos < 0.75:
        t = (pos - 0.50) / 0.25
        if abs(t - 0.5) < 0.3:
            return 1.08, "+10%"
        return 1.05 + (1.0 - abs(t - 0.5)) * 0.05, "+8%"
    if pos < 0.90:
        t = (pos - 0.75) / 0.15
        return 1.08 - t * 0.10, f"+{int(10 - t * 12)}%"
    t = (pos - 0.90) / 0.10
    return 0.98 - t * 0.06, f"-{int(t * 6)}%"


def _narrative_phase_adjustment(*, segment_idx: int, total_segments: int, emotion: str, track_key: str) -> tuple[str, float, str, float, str | None]:
    if total_segments <= 1:
        return ("hook", 1.03, "+6%", 0.92, "emphatic" if (emotion or "").strip().lower() == "neutral" else None)
    pos = float(segment_idx) / float(max(1, total_segments - 1))
    em = str(emotion or "neutral").strip().lower()
    k = str(track_key or "").strip().lower()
    if pos < 0.18:
        emo_hint = "emphatic" if em in ("neutral", "calm") else None
        if k == "emotion" and em in ("neutral", "calm"):
            emo_hint = "tense"
        return ("hook", 1.05, "+8%", 0.84, emo_hint)
    if pos > 0.84:
        emo_hint = "calm" if em in ("neutral", "tense", "emphatic") else None
        return ("outro", 0.94, "-6%", 1.20, emo_hint)
    return ("body", 1.0, "+0%", 1.0, None)


def _fmt_srt_ts(sec: float) -> str:
    t = max(0.0, float(sec or 0.0))
    hh = int(t // 3600)
    mm = int((t % 3600) // 60)
    ss = int(t % 60)
    ms = int(round((t - int(t)) * 1000.0))
    if ms >= 1000:
        ss += 1
        ms = 0
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def _subtitle_chunks(text: str) -> list[str]:
    return caption_pages(clean_tts_text(text), max_len=24)


def _calculate_text_complexity(text: str) -> float:
    t = str(text or "").strip()
    if not t:
        return 1.0
    punct_count = sum(1 for c in t if c in '，。！？、；：""''（）')
    punct_ratio = punct_count / max(1, len(t))
    num_count = sum(1 for c in t if c.isdigit())
    num_ratio = num_count / max(1, len(t))
    eng_count = sum(1 for c in t if ord(c) < 128 and c.isalpha())
    eng_ratio = eng_count / max(1, len(t))
    words = t.split()
    avg_word_len = sum(len(w) for w in words) / max(1, len(words))
    complexity = 1.0 + punct_ratio * 0.8 + num_ratio * 0.3 + eng_ratio * 0.5 + (avg_word_len - 3) * 0.1
    return max(0.5, min(1.5, complexity))


def _segments_to_srt(rows: list[tuple[float, float, str]], *, gap_ms: int = 30) -> str:
    out: list[str] = []
    idx = 0
    base_gap_s = max(0, min(200, int(gap_ms))) / 1000.0
    prev_text = ""
    for st, et, txt in rows:
        text = str(txt or "").strip()
        text = clean_tts_text(text)
        if not text or et <= st:
            continue
        complexity = _calculate_text_complexity(text)
        semantic_factor = 1.0
        if prev_text and text:
            continuity_markers = [
                r"^(而是|所以|但是|不过|可是|其实|才|就|却|反而|而且|接着|然后)",
                r"(不是.+而是|因为.+所以|如果.+就|虽然.+但是|不但.+而且)$",
            ]
            for pat in continuity_markers:
                if re.search(pat, text):
                    semantic_factor = 0.6
                    break
                if re.search(pat, prev_text + text):
                    semantic_factor = 0.65
                    break
            if semantic_factor >= 1.0:
                prev_words = set(prev_text[-5:] if len(prev_text) > 5 else prev_text)
                cur_start = text[: min(5, len(text))]
                if any(w in cur_start for w in prev_words if len(w) >= 2):
                    semantic_factor = 0.75
        effective_gap = base_gap_s * semantic_factor
        parts = _subtitle_chunks(text)
        if not parts:
            continue
        if len(parts) == 1:
            idx += 1
            out.extend([str(idx), f"{_fmt_srt_ts(float(st))} --> {_fmt_srt_ts(float(et))}", clean_subtitle_display_text(parts[0]), ""])
            prev_text = text
            continue
        total_chars = max(1, sum(max(1, len(p)) for p in parts))
        cur = float(st)
        total_span = max(0.2, float(et) - float(st))
        for i, part in enumerate(parts):
            weight = max(1, len(part)) / float(total_chars)
            span = max(0.72, total_span * weight)
            max_hold = max(1.1, total_span * 0.8)
            span = min(max_hold, span)
            end_at = float(et) if i == len(parts) - 1 else min(float(et), cur + span)
            if end_at <= cur:
                end_at = min(float(et), cur + max(0.72, total_span / len(parts)))
            if i < len(parts) - 1:
                dynamic_gap = effective_gap if complexity > 1.2 else base_gap_s
                end_at = max(cur + 0.68, min(end_at, float(et) - dynamic_gap))
            idx += 1
            out.extend([str(idx), f"{_fmt_srt_ts(cur)} --> {_fmt_srt_ts(end_at)}", clean_subtitle_display_text(part), ""])
            cur = min(float(et), end_at)
        prev_text = text
    return "\n".join(out).strip() + "\n"


def _ensure_wav(*, backend: str, offline_voice_id: str, edge_voice: str, rate: str, text: str, tempo: float, pitch: float, out_wav: Path, emotion: str = "neutral") -> None:
    text = clean_tts_text(text)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    tmp_wav = out_wav.with_name(out_wav.stem + ".tmp" + out_wav.suffix)
    if tmp_wav.exists():
        try:
            tmp_wav.unlink(missing_ok=True)
        except Exception:
            pass
    if backend == "edge":
        mp3 = out_wav.with_suffix(".mp3")

        def _cleanup_edge_intermediate() -> None:
            for p in (mp3, tmp_wav):
                try:
                    if p.exists():
                        p.unlink(missing_ok=True)
                except Exception:
                    pass

        def _generate_edge_mp3(*, allow_ssml: bool) -> None:
            try:
                if mp3.exists():
                    mp3.unlink(missing_ok=True)
            except Exception:
                pass
            edge_tts_audio_only(text=text, voice=edge_voice, rate=rate, audio_path=mp3, timeout_s=240)
            if (not mp3.exists()) or mp3.stat().st_size <= 0:
                raise RuntimeError(f"Edge TTS 未生成有效音频片段：{mp3.name}")

        last_error = ""
        for attempt, allow_ssml in enumerate((True, False), start=1):
            _cleanup_edge_intermediate()
            try:
                try:
                    _generate_edge_mp3(allow_ssml=allow_ssml)
                except Exception:
                    if allow_ssml:
                        edge_tts_audio_only(text=text, voice=edge_voice, rate=rate, audio_path=mp3, timeout_s=240)
                    else:
                        raise
                if (not mp3.exists()) or mp3.stat().st_size <= 0:
                    raise RuntimeError(f"Edge TTS 未生成有效音频片段：{mp3.name}")
                run_ffmpeg(["-y", "-i", ffmpeg_path(mp3), "-ac", "1", "-ar", "22050", ffmpeg_path(tmp_wav)])
                try:
                    mp3.unlink(missing_ok=True)
                except Exception:
                    pass
                # 在线配音模式仅使用在线音频，不再额外依赖 rubberband 做后处理，避免破坏仅在线链路的稳定性。
                tmp_wav.replace(out_wav)
                return
            except Exception as e:
                last_error = str(e).strip()
                logger.warning("Edge TTS 片段处理失败，第 {} 次尝试：{}", attempt, last_error[:240])
                _cleanup_edge_intermediate()
        raise RuntimeError(f"Edge TTS 片段处理失败：{mp3.name}；{last_error[:280]}")
    else:
        # 离线路径也严格使用原始语速，不再做 tempo/rubberband 后处理。
        offline_piper_audio_only(text=text, voice_id=offline_voice_id, wav_path=out_wav, length_scale=None)
        if not out_wav.exists():
            out_wav.write_bytes(b"")
        return
    tmp_wav.replace(out_wav)
