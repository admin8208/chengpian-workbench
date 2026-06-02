import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from app.db import session_scope
from app.models import Variant
from app.tasks_audio_helpers import AudioSubtitlePrepResultCompat, prepare_audio_and_subtitles as prepare_audio_and_subtitles_helper
from app.tasks_helpers import friendly_tts_failure_message as _friendly_tts_failure_message
from app.tasks_render import finalize_render_outputs as finalize_render_outputs_impl, rel_to_dir as rel_to_dir_impl, subtitle_has_visible_cues as subtitle_has_visible_cues_impl
from app.tasks_render_finalize import cleanup_non_cached_silent_track
from app.tasks_render_helpers import is_generated_render_rel_path as is_generated_render_rel_path_impl
from app.tasks_render_track import build_silent_video_track as build_silent_video_track_impl
from app.tasks_tts_pipeline import build_scene_srt_fallback as build_scene_srt_fallback_impl


@dataclass
class AudioSubtitlePrepResultBridge(AudioSubtitlePrepResultCompat):
    pass


def build_scene_srt_fallback_bridge(**kwargs) -> Path | None:
    return build_scene_srt_fallback_impl(**kwargs)


def prepare_audio_and_subtitles_bridge(**kwargs) -> AudioSubtitlePrepResultBridge:
    result = prepare_audio_and_subtitles_helper(
        **kwargs,
        friendly_tts_failure_message=_friendly_tts_failure_message,
        subtitle_has_visible_cues=subtitle_has_visible_cues_impl,
    )
    return AudioSubtitlePrepResultBridge(**result.__dict__)


def build_silent_video_track_bridge(**kwargs) -> Path:
    return build_silent_video_track_impl(**kwargs)


def finalize_render_outputs_bridge(*, cleanup_project_intermediate_artifacts, **kwargs) -> tuple[Path, Path | None]:
    return finalize_render_outputs_impl(**kwargs, is_generated_render_rel_path=is_generated_render_rel_path_impl, cleanup_project_intermediate_artifacts=cleanup_project_intermediate_artifacts)


def upsert_variant_bridge(project_id: int, *, kind: str, name: str, data: dict) -> None:
    with session_scope() as session:
        variant = Variant(project_id=project_id, kind=kind, name=name, data_json=json.dumps(data, ensure_ascii=True))
        session.add(variant)


def rel_to_dir_bridge(path: Path, base: Path) -> str:
    return rel_to_dir_impl(path, base)


def stable_digest_bridge(parts: list[object]) -> str:
    raw = "||".join(str(x or "") for x in parts)
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]


def cleanup_non_cached_silent_track_bridge(path: Path | None) -> None:
    cleanup_non_cached_silent_track(path)
