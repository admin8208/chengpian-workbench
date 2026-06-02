import json
import time
from pathlib import Path

from loguru import logger
from sqlmodel import select

from app.logging_setup import sanitize_log_text
from app.models import Asset
from app.tasks_tts_cache import build_generated_tts_cache_paths


def render_video_impl_runtime(
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
    abort_if_job_cancelled,
    now_utc,
    update_job,
    patch_job_payload,
    render_queue_manager,
    is_job_cancelled,
    wait_if_job_paused,
    session_scope,
    prepare_render_context,
    get_pack_impl,
    get_edge_voice_id,
    get_default_voice_rate,
    project_material_mode,
    scene_binding_material_mode,
    material_mode_label,
    update_job_in_session,
    asset_disk_path,
    project_exports_dir,
    clean_tts_text,
    stable_digest,
    project_audio_dir,
    project_subtitles_dir,
    prepare_audio_and_subtitles,
    humanize_render_error,
    build_silent_video_track,
    build_output_paths,
    prepare_subtitle_filters_impl,
    build_mux_plan,
    run_ffmpeg_mux_with_fallback_impl,
    extend_mux_meta,
    finalize_render_output_bundle,
    finalize_render_outputs,
    mark_project_ready_if_export,
    project_model,
    cleanup_non_cached_silent_track,
) -> None:
    render_queue_timeout_s = 600
    target_job_id = int(outer_job_id) if outer_job_id else int(job_id)
    render_slot_acquired = False
    if abort_if_job_cancelled(target_job_id):
        return
    render_token = f"j{int(target_job_id)}_{now_utc().strftime('%Y%m%d_%H%M%S_%f')}"
    silent_path: Path | None = None

    def _scale(p: int | None) -> int | None:
        if p is None:
            return None
        try:
            p2 = max(0, min(100, int(p)))
        except Exception:
            return None
        try:
            b = int(progress_base)
            s = int(progress_span)
        except Exception:
            b, s = 0, 100
        b = max(0, min(100, b))
        s = max(0, min(100, s))
        return max(0, min(100, b + int(p2 * (s / 100.0))))

    def _upd(*, status: str | None = None, progress: int | None = None, message: str | None = None) -> None:
        st = status
        if keep_running and st == "done":
            st = None
        update_job(
            target_job_id,
            status=st,
            progress=_scale(progress),
            message=message if message is not None else "",
        )

    def _mark_render_substage(name: str) -> None:
        try:
            patch_job_payload(int(target_job_id), {"render_substage": str(name or "")})
        except Exception:
            pass

    def _probe_media_duration(path: Path, *, kind: str) -> float:
        try:
            if (not path.exists()) or path.stat().st_size <= 0:
                return 0.0
            if kind == "audio":
                from moviepy import AudioFileClip as _AF

                clip = _AF(str(path))
            else:
                from moviepy import VideoFileClip as _VF

                clip = _VF(str(path))
            try:
                return float(getattr(clip, "duration", 0.0) or 0.0)
            finally:
                try:
                    clip.close()
                except Exception:
                    pass
        except Exception:
            return 0.0

    def _timeline_duration(base_durs: list[float]) -> float:
        try:
            return float(sum(max(0.0, float(x or 0.0)) for x in base_durs))
        except Exception:
            return 0.0

    def _duration_aligned(video_sec: float, audio_sec: float, *, tolerance_sec: float = 1.0) -> bool:
        if video_sec <= 0 or audio_sec <= 0:
            return True
        return float(video_sec) + float(tolerance_sec) >= float(audio_sec)

    wait_round = 0
    wait_started_at = time.time()
    acquire_render_slot = getattr(render_queue_manager, "acquire_render_slot", None)
    while True:
        can_run = acquire_render_slot(job_id=target_job_id) if callable(acquire_render_slot) else render_queue_manager.can_start_render(exclude_job_id=target_job_id)
        if can_run:
            render_slot_acquired = True
            break
        if is_job_cancelled(target_job_id):
            _upd(status="cancelled", progress=100, message="已取消")
            return
        wait_round += 1
        waited_s = max(0, int(time.time() - wait_started_at))
        if waited_s >= render_queue_timeout_s:
            _upd(status="failed", progress=100, message="渲染队列长时间繁忙，等待可用渲染槽超时，请稍后重试")
            return
        _upd(status="queued", progress=0, message=f"渲染队列繁忙，等待可用渲染槽（第 {wait_round} 次检查）")
        wait_if_job_paused(target_job_id)
        time.sleep(3.0)

    _upd(status="running", progress=1, message="正在渲染成片")
    try:
        from moviepy import AudioFileClip, ImageClip, VideoFileClip, concatenate_videoclips, vfx  # noqa: F401

        wait_if_job_paused(target_job_id)

        with session_scope() as session:
            prep_ctx = prepare_render_context(
                session=session,
                project_id=project_id,
                target_job_id=target_job_id,
                rcfg_override=rcfg_override,
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
            voice_volume = prep_ctx.voice_volume
            subtitle_style = prep_ctx.subtitle_style
            subtitle_overrides = prep_ctx.subtitle_overrides
            target_w = prep_ctx.target_w
            target_h = prep_ctx.target_h
            aspect = prep_ctx.aspect
            transition = prep_ctx.transition
            transition_sec = prep_ctx.transition_sec
            motion_zoom = prep_ctx.motion_zoom

            image_paths: list[Path] = []
            current_material_mode = project_material_mode(None, render_cfg=rcfg)
            for sc in scenes:
                if sc.image_asset_id:
                    asset = session.exec(select(Asset).where(Asset.id == sc.image_asset_id)).first()
                    if asset:
                        bound_mode = scene_binding_material_mode(sc) or current_material_mode
                        if current_material_mode != bound_mode:
                            update_job_in_session(
                                session,
                                target_job_id,
                                status="failed",
                                progress=100,
                                message=(
                                    f"镜头 {sc.idx} 当前绑定记录为{material_mode_label(bound_mode)}，"
                                    f"但项目处于{material_mode_label(current_material_mode)}。"
                                    "请改回与当前模式一致的镜头素材后再渲染。"
                                ),
                            )
                            return
                        path = asset_disk_path(str(asset.rel_path or ""), is_export=False)
                        if path.exists():
                            image_paths.append(path)
                            continue

                missing_label = "镜头图" if str((rcfg or {}).get("material_mode") or "").strip().lower() == "ai" else "素材"
                update_job_in_session(session, target_job_id, status="failed", progress=100, message=f"镜头 {sc.idx} 缺少可用{missing_label}，已停止渲染以避免黑页。请先补齐后再渲染。")
                return

            base_durs = [max(2.0, float(s.duration_sec or 4.0)) for s in scenes]
            planned_duration = float(sum(base_durs))

            script_text = (project.script or "").strip()
            if not script_text:
                script_text = "\n".join([s.narration.strip() for s in scenes if s.narration.strip()])
            script_text = clean_tts_text(script_text)
            if not script_text:
                update_job_in_session(session, target_job_id, status="failed", progress=100, message="没有可配音的脚本/旁白")
                return

            out_dir = project_exports_dir(pid)
            out_dir.mkdir(parents=True, exist_ok=True)

            _tts_cache_key, audio_path, srt_path = build_generated_tts_cache_paths(
                pid=pid,
                project_script=str(project.script or ""),
                voice_name=str(voice_name or ""),
                voice_rate=str(voice_rate or ""),
                channel_key=str(project.channel_key or ""),
                workflow=str(wf or "mix"),
                stable_digest=stable_digest,
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

            if require_existing_tts and not (has_voice_upload or has_subtitle_upload or (audio_path.exists() and srt_path.exists())):
                update_job_in_session(session, target_job_id, status="failed", progress=100, message="缺少已生成的配音/字幕产物，请先完成配音阶段后再继续渲染。")
                return

        tts_backend_used = ""
        if require_existing_tts:
            if outer_job_id:
                patch_job_payload(int(target_job_id), {"tts_done": True, "render_substage": "tts_ready"})
            _upd(progress=68, message="复用已生成配音/字幕，开始渲染视频")
        else:
            _mark_render_substage("tts_prepare")
            try:
                prep = prepare_audio_and_subtitles(
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
                    reuse_generated_tts=(reuse_generated_tts or (not has_voice_upload and not has_subtitle_upload and audio_path.exists() and srt_path.exists())),
                    temp_file_prefix=f"subtitle_{render_token}",
                    on_update=_upd,
                )
            except RuntimeError as exc:
                msg = str(exc)
                if msg == "cancelled":
                    _upd(status="cancelled", progress=100, message="已取消")
                else:
                    _upd(status="failed", progress=100, message=msg)
                return

            audio_path = prep.audio_path
            srt_path = prep.srt_path
            base_durs = prep.base_durs
            tts_backend_used = prep.tts_backend_used
            if outer_job_id:
                patch_job_payload(int(target_job_id), {"tts_done": True, "render_substage": "tts_ready"})
            _upd(progress=68, message="配音/字幕已完成，开始渲染视频")

        audio_duration = _probe_media_duration(audio_path, kind="audio")
        if audio_duration <= 0:
            audio_duration = _timeline_duration(base_durs) or planned_duration

        scenes_meta: list[dict] = []
        for sc in scenes:
            try:
                meta_obj = json.loads(sc.meta_json or "{}") if sc.meta_json else {}
            except Exception:
                meta_obj = {}
            scenes_meta.append(meta_obj)

        silent_cache_key = stable_digest([
            pid,
            target_w,
            target_h,
            transition,
            float(transition_sec),
            float(motion_zoom),
            f"audio:{str(audio_path)}:{float(audio_duration):.3f}",
            *(f"dur:{float(d or 0.0):.3f}" for d in base_durs),
            *(f"{int(getattr(sc, 'id', 0) or 0)}:{int(getattr(sc, 'image_asset_id', 0) or 0)}" for sc in scenes),
        ])
        cached_silent_path = out_dir / f"silent_cache_{silent_cache_key}.mp4"
        rebuild_cached_silent = False
        if cached_silent_path.exists() and cached_silent_path.is_file() and cached_silent_path.stat().st_size > 0:
            cached_video_duration = _probe_media_duration(cached_silent_path, kind="video")
            rebuild_cached_silent = not _duration_aligned(cached_video_duration, audio_duration)
        if cached_silent_path.exists() and cached_silent_path.is_file() and cached_silent_path.stat().st_size > 0 and not rebuild_cached_silent:
            silent_path = cached_silent_path
            _mark_render_substage("silent_track_ready")
            _upd(progress=82, message="复用已生成静音视频轨")
        else:
            _mark_render_substage("silent_track_prepare")
            try:
                silent_path = build_silent_video_track(
                    job_id=job_id,
                    target_job_id=target_job_id,
                    project_title=str(project.title or ""),
                    scenes=scenes,
                    image_paths=image_paths,
                    base_durs=base_durs,
                    target_w=target_w,
                    target_h=target_h,
                    transition=transition,
                    transition_sec=float(transition_sec),
                    motion_zoom=float(motion_zoom),
                    out_dir=out_dir,
                    silent_path=cached_silent_path,
                    on_update=_upd,
                    scenes_meta=scenes_meta,
                    wait_if_job_paused=wait_if_job_paused,
                    is_job_cancelled=is_job_cancelled,
                )
            except RuntimeError as exc:
                if str(exc) == "cancelled":
                    _upd(status="cancelled", progress=100, message="已取消")
                else:
                    _upd(status="failed", progress=100, message=humanize_render_error(str(exc)))
                return
            _mark_render_substage("silent_track_ready")
        _upd(progress=82, message="静音视频轨已完成")

        silent_duration = _probe_media_duration(silent_path, kind="video") if silent_path else 0.0
        if not _duration_aligned(silent_duration, audio_duration):
            _upd(status="failed", progress=100, message="视频轨短于主音频时间轴，已阻止输出截断成片。请重新生成视觉素材后再渲染。")
            return

        _mark_render_substage("mux_prepare")
        if tts_backend_used:
            _upd(progress=86, message=f"开始混音并烧录字幕（配音：{tts_backend_used}）")
        else:
            _upd(progress=86, message="开始混音并烧录字幕")
        if is_job_cancelled(job_id):
            _upd(status="cancelled", progress=100, message="已取消")
            return
        wait_if_job_paused(target_job_id)
        ts = now_utc().strftime("%Y%m%d_%H%M%S_%f")
        tag = str(export_tag or "export").strip().lower()

        output_paths = build_output_paths(out_dir=out_dir, export_tag=tag, ts=ts)
        out_file = output_paths.out_file
        out_tmp = output_paths.out_tmp

        vf, vf_retry = prepare_subtitle_filters_impl(srt_path, subtitle_style=subtitle_style, subtitle_overrides=subtitle_overrides, aspect=aspect)
        mux_plan = build_mux_plan(
            silent_path=silent_path,
            audio_path=audio_path,
            out_tmp=out_tmp,
            voice_volume=float(voice_volume),
            vf=vf,
        )

        try:
            mux_meta = run_ffmpeg_mux_with_fallback_impl(mux_plan.args, vf=vf, vf_retry=vf_retry, on_update=_upd)
        except RuntimeError as exc:
            _upd(status="failed", progress=100, message=humanize_render_error(str(exc)))
            return
        _upd(progress=92, message="音视频合成完成，写入最终成片")
        if is_job_cancelled(target_job_id):
            try:
                out_tmp.unlink(missing_ok=True)
            except Exception:
                pass
            _upd(status="cancelled", progress=100, message="已取消")
            return

        try:
            mux_meta = extend_mux_meta(
                mux_meta=mux_meta,
                target_w=int(target_w),
                target_h=int(target_h),
                aspect=str(aspect),
                transition=str(transition),
                transition_sec=float(transition_sec),
                motion_zoom=float(motion_zoom),
                subtitle_style=str(subtitle_style),
            )
        except Exception:
            pass
        finalized = finalize_render_output_bundle(
            is_job_cancelled=is_job_cancelled,
            target_job_id=target_job_id,
            out_tmp=out_tmp,
            mark_render_substage=_mark_render_substage,
            finalize_render_outputs=finalize_render_outputs,
            pid=pid,
            tag=tag,
            ts=ts,
            out_dir=out_dir,
            out_file=out_file,
            audio_path=audio_path,
            srt_path=srt_path,
            candidate_batch_id=candidate_batch_id,
            render_token=render_token,
            render_meta=mux_meta,
            on_cancel=lambda: _upd(status="cancelled", progress=100, message="已取消"),
        )
        if finalized is None:
            return
        out_file, history_path = finalized
        _upd(progress=96, message="最终成片已写入，整理输出记录")

        mark_project_ready_if_export(tag=tag, project_id=project_id, session_scope=session_scope, project_model=project_model)

        _mark_render_substage("done")
        _upd(status="done", progress=100, message="渲染完成：最终成片已生成")
    except Exception as exc:
        logger.exception(
            "render_video_impl_runtime failed job_id={} project_id={} target_job_id={} render_substage={} error={}",
            job_id,
            project_id,
            target_job_id,
            render_token,
            sanitize_log_text(exc),
        )
        try:
            patch_job_payload(
                int(target_job_id),
                {
                    "render_substage": "finalize_output",
                    "last_error": str(exc),
                },
            )
        except Exception:
            pass
        _upd(status="failed", progress=100, message=humanize_render_error(str(exc)))
    finally:
        if render_slot_acquired:
            try:
                release_render_slot = getattr(render_queue_manager, "release_render_slot", None)
                if callable(release_render_slot):
                    release_render_slot(job_id=target_job_id)
            except Exception:
                pass
        cleanup_non_cached_silent_track(silent_path)
