from __future__ import annotations

import json
from pathlib import Path

from app.api_common import cleanup_project_intermediate_artifacts
from app.api_common import register_project_tts_cache_refs
from app.db import session_scope
from app.huey_app import render_queue_manager
from app.jobs import abort_if_job_cancelled, is_job_cancelled, patch_job_payload, update_job, update_job_in_session, wait_if_job_paused
from app.material_policies import material_mode_label, project_material_mode, scene_binding_material_mode
from app.models import Asset, Project, Scene, Variant
from app.modules.tts.service import get_default_voice_rate, get_edge_voice_id
from app.project_paths import asset_disk_path, project_audio_dir, project_exports_dir, project_subtitles_dir, rel_to_projects_root
from app.subtitles import clean_tts_text
from app.tasks_audio_helpers import ensure_silent_voice_mp3 as ensure_silent_voice_mp3_helper
from app.tasks_autopilot import get_pack as get_pack_impl
from app.tasks_helpers import humanize_render_error as _humanize_render_error
from app.tasks_render import subtitle_has_visible_cues as subtitle_has_visible_cues_impl
from app.tasks_render_bridge import (
    build_scene_srt_fallback_bridge,
    build_silent_video_track_bridge,
    finalize_render_outputs_bridge,
    prepare_audio_and_subtitles_bridge,
    rel_to_dir_bridge,
    stable_digest_bridge,
)
from app.tasks_render_compose import build_mux_plan, build_output_paths, extend_mux_meta
from app.tasks_render_finalize import cleanup_non_cached_silent_track, finalize_render_output_bundle, mark_project_ready_if_export
from app.tasks_render_helpers import prepare_subtitle_filters as prepare_subtitle_filters_impl, run_ffmpeg_mux_with_fallback as run_ffmpeg_mux_with_fallback_impl
from app.tasks_render_prepare import prepare_render_context
from app.tasks_render_runtime import render_video_impl_runtime
from app.tasks_helpers import friendly_tts_failure_message as _friendly_tts_failure_message
from app.tasks_tts_cache import build_generated_tts_cache_paths
from app.tasks_tts_pipeline import prepare_audio_and_subtitles as prepare_audio_and_subtitles_impl
from app.time_utils import now_utc
from sqlmodel import select


def build_scene_srt_fallback_local(**kwargs) -> Path | None:
    return build_scene_srt_fallback_bridge(**kwargs)


def ensure_silent_voice_mp3_local(audio_path: Path, *, duration_sec: float) -> None:
    ensure_silent_voice_mp3_helper(audio_path, duration_sec=duration_sec)


def prepare_audio_and_subtitles_local(**kwargs):
    return prepare_audio_and_subtitles_bridge(**kwargs)


def build_silent_video_track_local(**kwargs) -> Path:
    return build_silent_video_track_bridge(**kwargs)


def finalize_render_outputs_local(*, cleanup_project_intermediate_artifacts=cleanup_project_intermediate_artifacts, **kwargs) -> tuple[Path, Path | None]:
    return finalize_render_outputs_bridge(cleanup_project_intermediate_artifacts=cleanup_project_intermediate_artifacts, **kwargs)


def upsert_variant_local(project_id: int, *, kind: str, name: str, data: dict) -> None:
    import json

    with session_scope() as session:
        variant = Variant(project_id=project_id, kind=kind, name=name, data_json=json.dumps(data, ensure_ascii=True))
        session.add(variant)


def rel_to_dir_local(path: Path, base: Path) -> str:
    return rel_to_dir_bridge(path, base)


def stable_digest_local(parts: list[object]) -> str:
    return stable_digest_bridge(parts)


def prepare_project_tts_local(
    job_id: int,
    project_id: int,
    *,
    progress_base: int = 0,
    progress_span: int = 100,
) -> None:
    def _scale(p: int | None) -> int | None:
        if p is None:
            return None
        try:
            p2 = max(0, min(100, int(p)))
            b = max(0, min(100, int(progress_base)))
            s = max(0, min(100, int(progress_span)))
        except Exception:
            return None
        return max(0, min(100, b + int(p2 * (s / 100.0))))

    def _upd(*, status: str | None = None, progress: int | None = None, message: str | None = None) -> None:
        update_job(job_id, status=status, progress=_scale(progress), message=message if message is not None else "")

    if abort_if_job_cancelled(job_id):
        return
    _upd(status="running", progress=1, message="正在生成配音/字幕")
    with session_scope() as session:
        prep_ctx = prepare_render_context(
            session=session,
            project_id=project_id,
            target_job_id=job_id,
            rcfg_override=None,
            get_pack=get_pack_impl,
            get_edge_voice_id=get_edge_voice_id,
            get_default_voice_rate=get_default_voice_rate,
        )
        if not prep_ctx:
            return
        project = prep_ctx.project
        pid = prep_ctx.pid
        wf = prep_ctx.wf
        rcfg = prep_ctx.rcfg
        scenes = prep_ctx.scenes
        voice_name = prep_ctx.voice_name
        voice_rate = prep_ctx.voice_rate
        script_text = clean_tts_text((project.script or "").strip() or "\n".join([s.narration.strip() for s in scenes if s.narration.strip()]))
        if not script_text:
            update_job_in_session(session, job_id, status="failed", progress=100, message="没有可配音的脚本/旁白")
            return
        base_durs = [max(2.0, float(s.duration_sec or 4.0)) for s in scenes]
        planned_duration = float(sum(base_durs))
        _tts_cache_key, audio_path, srt_path = build_generated_tts_cache_paths(
            pid=pid,
            project_script=str(project.script or ""),
            voice_name=str(voice_name or ""),
            voice_rate=str(voice_rate or ""),
            channel_key=str(project.channel_key or ""),
            workflow=str(wf or "mix"),
            stable_digest=stable_digest_local,
            project_audio_dir=project_audio_dir,
            project_subtitles_dir=project_subtitles_dir,
        )
        has_voice_upload = False
        has_subtitle_upload = False
        if project.voice_asset_id:
            asset = session.exec(select(Asset).where(Asset.id == project.voice_asset_id)).first()
            if asset:
                path = asset_disk_path(str(asset.rel_path or ""), is_export=False)
                if path.exists():
                    audio_path = path
                    has_voice_upload = True
        if project.subtitle_asset_id:
            asset = session.exec(select(Asset).where(Asset.id == project.subtitle_asset_id)).first()
            if asset:
                path = asset_disk_path(str(asset.rel_path or ""), is_export=False)
                if path.exists():
                    srt_path = path
                    has_subtitle_upload = True
        require_tts = bool(wf == "mix")
        if isinstance(rcfg, dict) and rcfg.get("require_tts") is not None:
            require_tts = bool(rcfg.get("require_tts"))
    try:
        prep = prepare_audio_and_subtitles_impl(
            job_id=job_id,
            target_job_id=job_id,
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
            reuse_generated_tts=(not has_voice_upload and not has_subtitle_upload and audio_path.exists() and srt_path.exists()),
            temp_file_prefix=f"autopilot_tts_{job_id}",
            on_update=_upd,
            friendly_tts_failure_message=_friendly_tts_failure_message,
            subtitle_has_visible_cues=subtitle_has_visible_cues_impl,
            stage_switch_to_render=False,
        )
    except RuntimeError as exc:
        msg = str(exc)
        if msg == "cancelled":
            _upd(status="cancelled", progress=100, message="已取消")
        else:
            _upd(status="failed", progress=100, message=msg)
        return

    current_audio_rel = rel_to_projects_root(prep.audio_path)
    current_subtitle_rel = rel_to_projects_root(prep.srt_path)
    with session_scope() as session:
        db_scenes = session.exec(select(Scene).where(Scene.project_id == pid).order_by(Scene.idx)).all()
        elapsed = 0.0
        for index, scene in enumerate(db_scenes):
            if index >= len(prep.base_durs):
                continue
            final_dur = max(0.2, float(prep.base_durs[index] or 0.0))
            scene.duration_sec = final_dur
            try:
                meta = json.loads(scene.meta_json or "{}") if scene.meta_json else {}
            except Exception:
                meta = {}
            if not isinstance(meta, dict):
                meta = {}
            meta["audio_start_sec"] = elapsed
            meta["audio_end_sec"] = elapsed + final_dur
            meta["audio_duration_sec"] = final_dur
            meta["timeline_finalized"] = True
            meta["timeline_source"] = "uploaded_audio" if project.voice_asset_id else "generated_tts"
            scene.meta_json = json.dumps(meta, ensure_ascii=False)
            session.add(scene)
            elapsed += final_dur
        for cleanup_tag in ("voice", "subtitle", "voice_generated", "subtitle_generated"):
            olds = session.exec(select(Asset).where(Asset.project_id == pid).where(Asset.tag == cleanup_tag)).all()
            for old in olds:
                old_rel = str(getattr(old, "rel_path", "") or "").strip()
                if cleanup_tag in ("voice", "voice_generated") and old_rel == current_audio_rel:
                    continue
                if cleanup_tag in ("subtitle", "subtitle_generated") and old_rel == current_subtitle_rel:
                    continue
                session.delete(old)
        if prep.audio_path.exists():
            audio_meta = '{"source":"tts_stage"}'
            register_project_tts_cache_refs(pid, [current_audio_rel])
            exists = session.exec(select(Asset).where(Asset.project_id == pid).where(Asset.tag == "voice_generated").where(Asset.rel_path == current_audio_rel)).first()
            if exists:
                exists.meta_json = audio_meta
                session.add(exists)
            else:
                session.add(Asset(kind="audio", rel_path=current_audio_rel, mime="audio/mpeg", project_id=pid, tag="voice_generated", meta_json=audio_meta))
        if prep.srt_path.exists():
            subtitle_meta = '{"source":"tts_stage"}'
            register_project_tts_cache_refs(pid, [current_subtitle_rel])
            exists = session.exec(select(Asset).where(Asset.project_id == pid).where(Asset.tag == "subtitle_generated").where(Asset.rel_path == current_subtitle_rel)).first()
            if exists:
                exists.meta_json = subtitle_meta
                session.add(exists)
            else:
                session.add(Asset(kind="other", rel_path=current_subtitle_rel, mime="text/plain", project_id=pid, tag="subtitle_generated", meta_json=subtitle_meta))
    patch_job_payload(job_id, {"tts_done": True})
    _upd(status="done", progress=100, message="配音/字幕已生成")


def render_video_impl_local(
    job_id: int,
    project_id: int,
    *,
    rcfg_override: dict | None = None,
    export_tag: str = "export",
    candidate_batch_id: str | None = None,
    outer_job_id: int | None = None,
    progress_base: int = 0,
    progress_span: int = 100,
    keep_running: bool = False,
    reuse_generated_tts: bool = False,
    require_existing_tts: bool = False,
) -> None:
    return render_video_impl_runtime(
        job_id,
        project_id,
        rcfg_override=rcfg_override,
        export_tag=export_tag,
        candidate_batch_id=candidate_batch_id,
        outer_job_id=outer_job_id,
        progress_base=progress_base,
        progress_span=progress_span,
        keep_running=keep_running,
        reuse_generated_tts=reuse_generated_tts,
        require_existing_tts=require_existing_tts,
        abort_if_job_cancelled=abort_if_job_cancelled,
        now_utc=now_utc,
        update_job=update_job,
        patch_job_payload=patch_job_payload,
        render_queue_manager=render_queue_manager,
        is_job_cancelled=is_job_cancelled,
        wait_if_job_paused=wait_if_job_paused,
        session_scope=session_scope,
        prepare_render_context=prepare_render_context,
        get_pack_impl=get_pack_impl,
        get_edge_voice_id=get_edge_voice_id,
        get_default_voice_rate=get_default_voice_rate,
        project_material_mode=project_material_mode,
        scene_binding_material_mode=scene_binding_material_mode,
        material_mode_label=material_mode_label,
        update_job_in_session=update_job_in_session,
        asset_disk_path=asset_disk_path,
        project_exports_dir=project_exports_dir,
        clean_tts_text=clean_tts_text,
        stable_digest=stable_digest_local,
        project_audio_dir=project_audio_dir,
        project_subtitles_dir=project_subtitles_dir,
        prepare_audio_and_subtitles=prepare_audio_and_subtitles_local,
        humanize_render_error=_humanize_render_error,
        build_silent_video_track=build_silent_video_track_local,
        build_output_paths=build_output_paths,
        prepare_subtitle_filters_impl=prepare_subtitle_filters_impl,
        build_mux_plan=build_mux_plan,
        run_ffmpeg_mux_with_fallback_impl=run_ffmpeg_mux_with_fallback_impl,
        extend_mux_meta=extend_mux_meta,
        finalize_render_output_bundle=finalize_render_output_bundle,
        finalize_render_outputs=finalize_render_outputs_local,
        mark_project_ready_if_export=mark_project_ready_if_export,
        project_model=Project,
        cleanup_non_cached_silent_track=cleanup_non_cached_silent_track,
    )


__all__ = [
    "build_scene_srt_fallback_local",
    "ensure_silent_voice_mp3_local",
    "prepare_audio_and_subtitles_local",
    "build_silent_video_track_local",
    "finalize_render_outputs_local",
    "upsert_variant_local",
    "rel_to_dir_local",
    "stable_digest_local",
    "prepare_project_tts_local",
    "render_video_impl_local",
]
