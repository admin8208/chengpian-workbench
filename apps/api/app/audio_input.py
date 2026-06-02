import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from faster_whisper import WhisperModel
from moviepy import AudioFileClip

from app.settings import settings
from app.time_utils import utc_iso_z


@dataclass
class AudioTranscriptionSegment:
    idx: int
    text: str
    start_sec: float
    end_sec: float
    duration_sec: float


@dataclass
class AudioTranscriptionResult:
    full_text: str
    segments: list[AudioTranscriptionSegment]
    audio_duration: float


_ASR_MODEL = None


def _asr_cache_dir() -> Path:
    p = settings.data_dir / "tools" / "asr_cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _asr_model_cache_dir() -> Path:
    p = settings.data_dir / "tools" / "asr_models"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _audio_cache_key(audio_path: Path) -> str:
    h = hashlib.sha256()
    with audio_path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()[:32]


def _cache_path(audio_path: Path) -> Path:
    return _asr_cache_dir() / f"{_audio_cache_key(audio_path)}.json"


def _legacy_cache_path(audio_path: Path) -> Path:
    st = audio_path.stat()
    raw = f"{audio_path.resolve()}|{int(st.st_size)}|{int(st.st_mtime_ns)}"
    return _asr_cache_dir() / f"{hashlib.sha256(raw.encode('utf-8', errors='ignore')).hexdigest()[:32]}.json"


def _result_to_dict(result: AudioTranscriptionResult) -> dict:
    return {
        "full_text": result.full_text,
        "audio_duration": float(result.audio_duration or 0.0),
        "segments": [
            {
                "idx": int(seg.idx),
                "text": seg.text,
                "start_sec": float(seg.start_sec or 0.0),
                "end_sec": float(seg.end_sec or 0.0),
                "duration_sec": float(seg.duration_sec or 0.0),
            }
            for seg in result.segments
        ],
        "cached_at": utc_iso_z(),
    }


def _result_from_dict(obj: dict) -> AudioTranscriptionResult:
    segments = [
        AudioTranscriptionSegment(
            idx=int(item.get("idx") or 0),
            text=str(item.get("text") or ""),
            start_sec=float(item.get("start_sec") or 0.0),
            end_sec=float(item.get("end_sec") or 0.0),
            duration_sec=float(item.get("duration_sec") or 0.0),
        )
        for item in (obj.get("segments") or [])
        if isinstance(item, dict)
    ]
    return AudioTranscriptionResult(
        full_text=str(obj.get("full_text") or ""),
        segments=segments,
        audio_duration=float(obj.get("audio_duration") or 0.0),
    )


def _load_cached_result(audio_path: Path) -> AudioTranscriptionResult | None:
    try:
        for p in (_cache_path(audio_path), _legacy_cache_path(audio_path)):
            if not p.exists() or not p.is_file() or p.stat().st_size <= 0:
                continue
            obj = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(obj, dict):
                continue
            return _result_from_dict(obj)
    except Exception:
        return None


def _save_cached_result(audio_path: Path, result: AudioTranscriptionResult) -> None:
    try:
        p = _cache_path(audio_path)
        p.write_text(json.dumps(_result_to_dict(result), ensure_ascii=True), encoding="utf-8")
    except Exception:
        return


def _load_asr_model() -> WhisperModel:
    global _ASR_MODEL
    if _ASR_MODEL is None:
        try:
            _ASR_MODEL = WhisperModel(
                "Systran/faster-whisper-base",
                device="cpu",
                compute_type="int8",
                download_root=str(_asr_model_cache_dir()),
            )
        except Exception as e:
            raise RuntimeError(
                "音频转写模型加载失败：当前需要首次下载 faster-whisper-base 模型。请确认本机网络可访问 HuggingFace 或可用镜像源，并检查 data/tools/asr_models 目录可写。模型下载完成后再次重试即可。"
            ) from e
    return _ASR_MODEL


def _normalize_segment_text(text: str) -> str:
    return " ".join(str(text or "").replace("\n", " ").split()).strip()


def _split_long_segment(text: str, start_sec: float, end_sec: float, next_idx: int) -> list[AudioTranscriptionSegment]:
    text = _normalize_segment_text(text)
    if not text:
        return []
    pieces = [x.strip() for x in text.replace("！", "。 ").replace("？", "。 ").replace("；", "。 ").split("。") if x.strip()]
    if len(pieces) <= 1:
        pieces = [x.strip() for x in text.split("，") if x.strip()]
    if len(pieces) <= 1:
        pieces = [text]
    total = max(0.6, float(end_sec) - float(start_sec))
    weights = [max(1, len(piece)) for piece in pieces]
    sw = max(1, sum(weights))
    out: list[AudioTranscriptionSegment] = []
    cursor = float(start_sec)
    idx = next_idx
    for pos, piece in enumerate(pieces):
        portion = total * (weights[pos] / sw)
        seg_end = float(end_sec) if pos == len(pieces) - 1 else min(float(end_sec), cursor + portion)
        duration = max(1.2, seg_end - cursor)
        out.append(AudioTranscriptionSegment(idx=idx, text=piece, start_sec=cursor, end_sec=cursor + duration, duration_sec=duration))
        cursor += duration
        idx += 1
    if out:
        out[-1].end_sec = float(end_sec)
        out[-1].duration_sec = max(1.2, float(end_sec) - out[-1].start_sec)
    return out


def transcribe_audio_to_segments(audio_path: Path) -> AudioTranscriptionResult:
    cached = _load_cached_result(audio_path)
    if cached is not None:
        return cached
    model = _load_asr_model()
    audio_duration = 0.0
    with AudioFileClip(str(audio_path)) as clip:
        audio_duration = float(clip.duration or 0.0)
    segments: list[AudioTranscriptionSegment] = []
    full_text_parts: list[str] = []
    try:
        raw_segments, _info = model.transcribe(
            str(audio_path),
            language="zh",
            task="transcribe",
            beam_size=5,
            vad_filter=True,
        )
    except Exception as e:
        raise RuntimeError(
            "音频转写失败：请确认音频文件可读、模型已下载完成，或稍后重试。"
        ) from e
    next_idx = 1
    for raw in raw_segments:
        text = _normalize_segment_text(getattr(raw, "text", ""))
        if not text:
            continue
        start_sec = float(getattr(raw, "start", 0.0) or 0.0)
        end_sec = float(getattr(raw, "end", start_sec) or start_sec)
        if end_sec <= start_sec:
            continue
        full_text_parts.append(text)
        duration = end_sec - start_sec
        if duration > 10.0 or len(text) > 44:
            split_items = _split_long_segment(text, start_sec, end_sec, next_idx)
            segments.extend(split_items)
            next_idx += len(split_items)
            continue
        segments.append(AudioTranscriptionSegment(idx=next_idx, text=text, start_sec=start_sec, end_sec=end_sec, duration_sec=max(1.2, duration)))
        next_idx += 1
    full_text = _normalize_segment_text(" ".join(full_text_parts))
    if not segments and full_text:
        seg_count = max(1, min(8, math.ceil(max(1.0, audio_duration) / 6.0)))
        duration_per = max(2.0, float(audio_duration or 6.0) / seg_count)
        text_parts = _split_long_segment(full_text, 0.0, max(float(audio_duration or duration_per), duration_per * seg_count), 1)
        segments = text_parts[:]
    result = AudioTranscriptionResult(full_text=full_text, segments=segments, audio_duration=float(audio_duration or 0.0))
    _save_cached_result(audio_path, result)
    return result
