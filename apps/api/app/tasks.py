
import json
import hashlib
import math
import os
import random
import re
import shutil
import time
import zipfile
import base64
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from huey import crontab
from sqlmodel import select

from app.tasks_helpers import (
    naturalize_voice_rate as _naturalize_voice_rate,
    friendly_tts_failure_message as _friendly_tts_failure_message,
    humanize_render_error as _humanize_render_error,
    classify_media_provider_error as _classify_media_provider_error,
    fail_job as _fail_job,
)

from app.db import session_scope
from app.jobs import abort_if_job_cancelled, acquire_job_lease, clear_job_lease_if_terminal, get_job_payload, is_job_cancelled, is_job_cancelled_in_session, patch_job_payload, update_job, update_job_in_session, wait_if_job_paused
from app.models import Asset, ChannelPack, Job, LlmProvider, Project, Scene, Variant
from app.huey_app import huey, render_queue_manager
from app.settings import settings
from app.api_common import cleanup_project_intermediate_artifacts, default_render_dimensions, project_render_aspect
from app.ffmpeg_utils import ffmpeg_path, run_ffmpeg
from app.http_client import new_session
from app.modules.media.library_import import ImportRequest, import_to_project
from app.modules.media.service import get_media_api_key, has_media_api_key
from app.subtitles import clean_tts_text, naive_srt_from_lines, naive_srt_from_scenes, normalize_subtitle_settings, subtitle_force_style, vtt_to_srt
from app.modules.tts.runtime import edge_tts_to_files
from app.modules.tts.service import get_default_voice_rate, get_edge_voice_id
from app.modules.media.web_search import search_web_media, search_web_media_parallel, supported_providers
from app.llm_client import LlmChatMessage, LlmError, ollama_chat_json, openai_compat_chat_json, openai_compat_generate_image
from app.llm_service import get_api_key, get_default_provider
from app.material_policies import material_mode_label, project_material_mode, scene_binding_material_mode
from app.project_paths import asset_disk_path, project_audio_dir, project_exports_dir, project_generated_dir, project_subtitles_dir, rel_to_projects_root
from app.compliance import check_text
from app.prompts import (
    PROMPT_META_WRITER_GENERATE,
    PROMPT_META_WRITER_REWRITE,
    build_rewrite_storyboard_messages,
    track_query_bias,
)
from app.storyboard_postprocess import (
    default_search_en_from_query,
    enrich_storyboard_continuity,
    humanize_scene_durations,
    normalize_storyboard_output,
    normalize_storyboard_scene_durations,
    search_en_from_visual_intent,
)
from app.storyboard_service import generate_storyboard_via_llm
from app.tasks_storyboard import (
    de_ai_phrase as storyboard_de_ai_phrase,
    gen_script_and_scenes as storyboard_gen_script_and_scenes,
    llm_generate_storyboard as storyboard_llm_generate_storyboard,
    llm_rewrite_storyboard as storyboard_llm_rewrite_storyboard,
    storyboard_duration_profile,
)
from app.tasks_storyboard_entry_impl import (
    generate_storyboard_local as generate_storyboard_impl_local,
    rewrite_storyboard_local as rewrite_storyboard_impl_local,
)
from app.tasks_autopilot import (
    AUTOPILOT_STAGES,
    autopilot_get_job_status as autopilot_get_job_status_impl,
    autopilot_mark_stage as autopilot_mark_stage_impl,
    autopilot_payload as autopilot_payload_impl,
    autopilot_resume_stage as autopilot_resume_stage_impl,
    autopilot_run_impl,
    autopilot_scene_stats as autopilot_scene_stats_impl,
    autopilot_stage_done as autopilot_stage_done_impl,
    get_pack as get_pack_impl,
    run_autopilot_media_stage as run_autopilot_media_stage_impl,
    run_autopilot_render_stage as run_autopilot_render_stage_impl,
    run_autopilot_storyboard_stage as run_autopilot_storyboard_stage_impl,
    save_autopilot_storyboard as save_autopilot_storyboard_impl,
)
from app.tasks_autopilot_entry_impl import autopilot_run_local as autopilot_run_impl_local
from app.tasks_render import (
    finalize_render_outputs as finalize_render_outputs_impl,
    rel_to_dir as rel_to_dir_impl,
    score_candidate_video as score_candidate_video_impl,
    subtitle_has_visible_cues as subtitle_has_visible_cues_impl,
)
from app.tasks_tts_pipeline import (
    AudioSubtitlePrepResult,
    build_scene_srt_fallback as build_scene_srt_fallback_impl,
    ensure_silent_voice_mp3 as ensure_silent_voice_mp3_impl,
    prepare_audio_and_subtitles as prepare_audio_and_subtitles_impl,
    subtitle_alignment_ok as subtitle_alignment_ok_impl,
    subtitle_stats as subtitle_stats_impl,
    subtitle_text_coverage_ok as subtitle_text_coverage_ok_impl,
)
from app.time_utils import now_utc
from app.tasks_render_helpers import (
    is_generated_render_rel_path as is_generated_render_rel_path_impl,
    prepare_subtitle_filters as prepare_subtitle_filters_impl,
    run_ffmpeg_mux_with_fallback as run_ffmpeg_mux_with_fallback_impl,
)
from app.tasks_audio_helpers import (
    AudioSubtitlePrepResultCompat,
    ensure_silent_voice_mp3 as ensure_silent_voice_mp3_helper,
    prepare_audio_and_subtitles as prepare_audio_and_subtitles_helper,
)
from app.tasks_render_track import build_silent_video_track as build_silent_video_track_impl
from app.tasks_render_prepare import prepare_render_context
from app.tasks_media_queries import (
    build_query_candidates as build_query_candidates_helper,
    clean_query as clean_query_helper,
    llm_extra_queries as llm_extra_queries_helper,
    looks_english as looks_english_helper,
)
from app.tasks_media_binding import (
    library_asset_allowed as library_asset_allowed_helper,
    pick_main_library_hit as pick_main_library_hit_helper,
    pick_main_web_item as pick_main_web_item_helper,
    record_failed_scene as record_failed_scene_helper,
    search_library_assets as search_library_assets_helper,
    set_scene_asset as set_scene_asset_helper,
)
from app.tasks_media_search import (
    active_providers_for_query as active_providers_for_query_helper,
    llm_pick_best as llm_pick_best_helper,
    mark_provider_failure as mark_provider_failure_helper,
    rank_items as rank_items_helper,
    search_all as search_all_helper,
    search_images_only as search_images_only_helper,
)
from app.tasks_media_rewrite import (
    generate_keyword_variants as generate_keyword_variants_helper,
    rewrite_to_en_keywords as rewrite_to_en_keywords_helper,
)
from app.tasks_media_scene_flow import retry_scene_candidates, search_scene_candidates
from app.tasks_media_import_flow import apply_imported_asset, import_candidate_assets
from app.tasks_image_facade import (
    download_or_decode_image_local,
    generate_images_impl_local,
    generate_scene_image_via_provider_local,
    guess_image_ext_local,
    image_generate_attempts_local,
    image_generate_timeout_s_local,
    is_retryable_image_generation_error_local,
    normalize_image_size_local,
    pack_prompts,
    project_material_mode_local,
    scene_prompt_for_provider_local,
)
from app.project_summary_metrics import summary_continuity_metrics
from app.tasks_storyboard_bridge import (
    generate_storyboard_local_bridge,
    llm_generate_storyboard_bridge,
    llm_rewrite_storyboard_bridge,
    rewrite_storyboard_local_bridge,
    storyboard_duration_profile_bridge,
)
from app.tasks_image_bridge import (
    download_or_decode_image_bridge,
    generate_images_impl_bridge,
    generate_project_images_local_bridge,
    generate_scene_image_local_bridge,
    generate_scene_image_via_provider_bridge,
    guess_image_ext_bridge,
    image_generate_attempts_bridge,
    image_generate_timeout_s_bridge,
    is_retryable_image_generation_error_bridge,
    normalize_image_size_bridge,
    scene_prompt_for_provider_bridge,
    should_generate_scene_bridge,
)
from app.tasks_render_compose import (
    build_mux_plan,
    build_output_paths,
    extend_mux_meta,
)
from app.tasks_render_finalize import (
    cleanup_non_cached_silent_track,
    finalize_render_output_bundle,
    mark_project_ready_if_export,
)
from app.tasks_render_facade import (
    build_scene_srt_fallback_local,
    build_silent_video_track_local,
    ensure_silent_voice_mp3_local,
    finalize_render_outputs_local,
    prepare_audio_and_subtitles_local,
    rel_to_dir_local,
    stable_digest_local,
    upsert_variant_local,
)
from app.tasks_render_facade import render_video_impl_local
from app.tasks_media_runtime import autofill_media_impl_runtime
from app.tasks_media_facade import autofill_media_impl_local, autofill_media_local, get_project_media_plan_local, get_role_asset_path_local



def _storyboard_duration_profile(pack: ChannelPack, cfg: dict | None = None, *, render_cfg: dict | None = None) -> dict:
    from app.tasks_storyboard_bridge import storyboard_duration_profile_bridge

    return storyboard_duration_profile_bridge(pack, cfg, render_cfg=render_cfg)


def _run_autopilot_storyboard_stage(
    *,
    job_id: int,
    pid: int,
    title: str,
    src: str,
    channel_key: str,
    character_profile: str,
    wf: str,
    pack: ChannelPack,
    provider: LlmProvider | None,
    api_key: str,
    render_cfg: dict | None,
) -> None:
    from app.tasks_autopilot_facade import run_autopilot_storyboard_stage_local
    from app.tasks_storyboard_bridge import llm_generate_storyboard_bridge, llm_rewrite_storyboard_bridge

    return run_autopilot_storyboard_stage_local(job_id=job_id, pid=pid, title=title, src=src, channel_key=channel_key, character_profile=character_profile, wf=wf, pack=pack, provider=provider, api_key=api_key, render_cfg=render_cfg, llm_rewrite_storyboard=llm_rewrite_storyboard_bridge, llm_generate_storyboard=llm_generate_storyboard_bridge)
def _should_generate_scene(*, scene: Scene, force: bool) -> bool:
    return should_generate_scene_bridge(scene=scene, force=force)


def _run_autopilot_render_stage(
    *,
    job_id: int,
    project_id: int,
    pid: int,
    candidate_batch_id: str,
    resume_from_stage: str | None,
) -> None:
    from app.tasks_autopilot_facade import run_autopilot_render_stage_local

    return run_autopilot_render_stage_local(job_id=job_id, project_id=project_id, pid=pid, candidate_batch_id=candidate_batch_id, resume_from_stage=resume_from_stage, render_video_impl=render_video_impl_local)


@dataclass
class _AudioSubtitlePrepResult(AudioSubtitlePrepResultCompat):
    pass




def _build_scene_srt_fallback(
    *,
    pid: int,
    name: str,
    scene_texts: list[str],
    base_durs: list[float],
    script_text: str,
    audio_duration: float,
) -> Path | None:
    return build_scene_srt_fallback_local(pid=pid, name=name, scene_texts=scene_texts, base_durs=base_durs, script_text=script_text, audio_duration=audio_duration)


def _ensure_silent_voice_mp3(audio_path: Path, *, duration_sec: float) -> None:
    ensure_silent_voice_mp3_local(audio_path, duration_sec=duration_sec)


def _prepare_audio_and_subtitles(
    *,
    job_id: int,
    target_job_id: int,
    pid: int,
    project,
    scenes,
    script_text: str,
    audio_path: Path,
    srt_path: Path,
    has_voice_upload: bool,
    has_subtitle_upload: bool,
    require_tts: bool,
    planned_duration: float,
    base_durs: list[float],
    voice_name: str,
    voice_rate: str,
    reuse_generated_tts: bool,
    temp_file_prefix: str,
    on_update,
) -> _AudioSubtitlePrepResult:
    result = prepare_audio_and_subtitles_local(
        job_id=job_id,
        target_job_id=target_job_id,
        pid=pid,
        project=project,
        scenes=scenes,
        script_text=script_text,
        audio_path=audio_path,
        srt_path=srt_path,
        has_voice_upload=has_voice_upload,
        has_subtitle_upload=has_subtitle_upload,
        require_tts=require_tts,
        planned_duration=planned_duration,
        base_durs=base_durs,
        voice_name=voice_name,
        voice_rate=voice_rate,
        reuse_generated_tts=reuse_generated_tts,
        temp_file_prefix=temp_file_prefix,
        on_update=on_update,
        friendly_tts_failure_message=_friendly_tts_failure_message,
        subtitle_has_visible_cues=subtitle_has_visible_cues_impl,
    )
    return _AudioSubtitlePrepResult(**result.__dict__)


def _build_silent_video_track(
    *,
    job_id: int,
    target_job_id: int,
    project_title: str,
    scenes,
    image_paths: list[Path],
    base_durs: list[float],
    target_w: int,
    target_h: int,
    transition: str,
    transition_sec: float,
    motion_zoom: float,
    out_dir: Path,
    silent_path: Path,
    on_update,
    scenes_meta: list[dict] | None = None,
) -> Path:
    return build_silent_video_track_local(
        job_id=job_id,
        target_job_id=target_job_id,
        project_title=project_title,
        scenes=scenes,
        image_paths=image_paths,
        base_durs=base_durs,
        target_w=target_w,
        target_h=target_h,
        transition=transition,
        transition_sec=transition_sec,
        motion_zoom=motion_zoom,
        out_dir=out_dir,
        silent_path=silent_path,
        on_update=on_update,
        scenes_meta=scenes_meta,
        wait_if_job_paused=wait_if_job_paused,
        is_job_cancelled=is_job_cancelled,
    )


def _finalize_render_outputs(
    *,
    pid: int,
    tag: str,
    ts: str,
    out_dir: Path,
    out_file: Path,
    out_tmp: Path,
    audio_path: Path,
    srt_path: Path,
    candidate_batch_id: str | None,
    render_job_id: int,
    render_token: str,
    render_meta: dict | None = None,
) -> tuple[Path, Path | None]:
    return finalize_render_outputs_local(
        cleanup_project_intermediate_artifacts=cleanup_project_intermediate_artifacts,
        pid=pid,
        tag=tag,
        ts=ts,
        out_dir=out_dir,
        out_file=out_file,
        out_tmp=out_tmp,
        audio_path=audio_path,
        srt_path=srt_path,
        candidate_batch_id=candidate_batch_id,
        render_job_id=render_job_id,
        render_token=render_token,
        render_meta=render_meta,
    )


def _upsert_variant(project_id: int, *, kind: str, name: str, data: dict) -> None:
    upsert_variant_local(project_id, kind=kind, name=name, data=data)



def _autopilot_job_guard_reason(job_id: int, project_id: int) -> str | None:
    from app.tasks_autopilot_facade import autopilot_job_guard_reason_local

    return autopilot_job_guard_reason_local(job_id, project_id)


def _pack_prompts(pack: ChannelPack, scene: Scene) -> tuple[str, str]:
    return pack_prompts(pack, scene)


def _project_material_mode(project: Project | None) -> str:
    return project_material_mode_local(project)


def _normalize_image_size(project: Project | None) -> str:
    return normalize_image_size_local(project)


def _image_generate_timeout_s() -> int:
    return image_generate_timeout_s_local()


def _image_generate_attempts() -> int:
    return image_generate_attempts_local()


def _scene_prompt_for_provider(pack: ChannelPack, scene: Scene) -> str:
    return scene_prompt_for_provider_local(pack, scene)


def _download_or_decode_image(obj: dict) -> tuple[bytes, str]:
    return download_or_decode_image_local(obj)


def _guess_image_ext(mime: str, obj: dict) -> str:
    return guess_image_ext_local(mime, obj)


def _is_retryable_image_generation_error(detail: str) -> bool:
    return is_retryable_image_generation_error_local(detail)


def _generate_scene_image_via_provider(*, session, provider, api_key: str, project: Project, pack: ChannelPack, scene: Scene) -> tuple[bytes, str, dict]:
    return generate_scene_image_via_provider_local(session=session, provider=provider, api_key=api_key, project=project, pack=pack, scene=scene)


def _generate_images_impl(
    *,
    job_id: int,
    project_id: int,
    scene_ids: list[int] | None,
    force: bool,
    manage_job_state: bool = True,
) -> None:
    generate_images_impl_local(job_id=job_id, project_id=project_id, scene_ids=scene_ids, force=force, manage_job_state=manage_job_state)
generate_project_images_impl_local = generate_project_images_local_bridge
generate_scene_image_impl_local = generate_scene_image_local_bridge
