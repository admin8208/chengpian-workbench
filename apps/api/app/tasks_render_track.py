import json
import random
import shutil
from pathlib import Path

from app.ffmpeg_utils import ffmpeg_path, run_ffmpeg
from app.time_utils import now_utc


def build_silent_video_track(
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
    wait_if_job_paused,
    is_job_cancelled,
) -> Path:
    fps = 60

    def _is_video(path: Path) -> bool:
        return path.suffix.lower() in (".mp4", ".webm", ".mov", ".mkv", ".ogv")

    def _probe_duration_sec(path: Path) -> float:
        try:
            from moviepy import VideoFileClip as _VF

            clip = _VF(str(path))
            dur = float(getattr(clip, "duration", 0.0) or 0.0)
            try:
                clip.close()
            except Exception:
                pass
            return dur
        except Exception:
            return 0.0

    def _scene_meta_obj(scene) -> dict:
        try:
            obj = json.loads(getattr(scene, "meta_json", "{}") or "{}")
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    def _merged_scene_meta(index: int) -> dict:
        meta_from_scene = _scene_meta_obj(scenes[index])
        if isinstance(scenes_meta, list) and index < len(scenes_meta) and isinstance(scenes_meta[index], dict):
            merged = dict(meta_from_scene)
            merged.update(scenes_meta[index])
            return merged
        return meta_from_scene

    def _render_meta(meta: dict) -> dict:
        render_obj = meta.get("render") if isinstance(meta.get("render"), dict) else {}
        return render_obj

    def _visual_meta(meta: dict) -> dict:
        visual_obj = meta.get("visual") if isinstance(meta.get("visual"), dict) else {}
        return visual_obj

    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _scene_vf() -> str:
        return (
            f"scale={int(target_w)}:{int(target_h)}:force_original_aspect_ratio=increase,"
            f"crop={int(target_w)}:{int(target_h)},"
            f"setsar=1,unsharp=5:5:0.8:3"
        )

    def _compute_dynamic_transition(prev_meta: dict, cur_meta: dict, default_transition: str, default_sec: float) -> tuple[str, float]:
        try:
            prev_visual = _visual_meta(prev_meta)
            cur_visual = _visual_meta(cur_meta)
            prev_theme = str(prev_meta.get("visual_theme") or prev_visual.get("color_mood") or "").strip().lower()
            cur_theme = str(cur_meta.get("visual_theme") or cur_visual.get("color_mood") or "").strip().lower()
            prev_group = int(prev_meta.get("scene_group", 0) or 0)
            cur_group = int(cur_meta.get("scene_group", 0) or 0)
            cur_hint = str(cur_meta.get("transition_hint") or cur_visual.get("transition_hint") or "").strip().lower()

            if cur_hint == "continue":
                return ("crossfade", 0.28)
            if cur_hint == "contrast":
                return ("crossfade", 0.12)
            if cur_hint == "cut":
                return ("none", 0.0)
            if prev_group == cur_group and prev_group > 0:
                return ("crossfade", 0.26)
            if prev_theme == cur_theme and prev_theme:
                return ("crossfade", 0.18)
            return (default_transition, default_sec)
        except Exception:
            return (default_transition, default_sec)

    def _motion_mode(meta: dict, index: int) -> str:
        render_obj = _render_meta(meta)
        visual = _visual_meta(meta)
        explicit = str(render_obj.get("motion_mode") or visual.get("motion_mode") or visual.get("motion_intent") or "").strip().lower()
        if explicit in ("push_in", "pull_out", "pan_left", "pan_right"):
            return explicit
        transition_hint = str(meta.get("transition_hint") or "").strip().lower()
        if transition_hint == "continue":
            return "push_in"
        if transition_hint == "contrast":
            return "pull_out"
        if transition_hint == "cut":
            return "pan_left" if index % 2 else "pan_right"
        return "pan_right" if index % 2 else "pan_left"

    def _image_motion_vf(meta: dict, *, dur_s: float, index: int) -> str:
        motion_amount = _clamp(float(motion_zoom or 0.0), 0.0, 0.2)
        if motion_amount <= 0.0001:
            return _scene_vf()

        frame_count = max(2, int(round(dur_s * fps)))
        frame_span = max(1, frame_count - 1)
        overscan = 1.0 + motion_amount + (0.02 if dur_s >= 4.0 else 0.0)
        base_w = int(round(target_w * overscan))
        base_h = int(round(target_h * overscan))
        mode = _motion_mode(meta, index)

        if mode == "push_in":
            zoom_start = 1.0
            zoom_end = 1.0 + max(0.03, min(0.1, motion_amount * 0.9))
            z_expr = f"if(eq(on,1),{zoom_start:.4f},min(zoom+{((zoom_end - zoom_start) / frame_span):.5f},{zoom_end:.4f}))"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = "ih/2-(ih/zoom/2)"
        elif mode == "pull_out":
            zoom_start = 1.0 + max(0.03, min(0.1, motion_amount * 0.9))
            z_expr = f"if(eq(on,1),{zoom_start:.4f},max(zoom-{((zoom_start - 1.0) / frame_span):.5f},1.0000))"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = "ih/2-(ih/zoom/2)"
        elif mode == "pan_left":
            z_expr = "if(eq(on,1),1.0250,zoom)"
            x_expr = f"(iw-iw/zoom)*(1-((on-1)/{frame_span}))"
            y_expr = "(ih-ih/zoom)/2"
        else:
            z_expr = "if(eq(on,1),1.0250,zoom)"
            x_expr = f"(iw-iw/zoom)*((on-1)/{frame_span})"
            y_expr = "(ih-ih/zoom)/2"

        return (
            f"scale={base_w}:{base_h}:force_original_aspect_ratio=increase,"
            f"crop={base_w}:{base_h},"
            f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={frame_count}:s={int(target_w)}x{int(target_h)}:fps={fps},"
            f"setsar=1,unsharp=5:5:0.8:3"
        )

    clip_plan: list[tuple[float | None, float | None]] = [(None, None) for _ in range(len(scenes))]
    scene_meta_list: list[dict] = []
    try:
        for index, scene in enumerate(scenes):
            meta_obj = _merged_scene_meta(index)
            scene_meta_list.append(meta_obj)
            render_meta = _render_meta(meta_obj)
            start = render_meta.get("clip_start_sec")
            end = render_meta.get("clip_end_sec")
            try:
                start_f = float(start) if start is not None else None
            except Exception:
                start_f = None
            try:
                end_f = float(end) if end is not None else None
            except Exception:
                end_f = None
            if start_f is not None and end_f is not None and end_f > start_f:
                clip_plan[index] = (start_f, end_f)
    except Exception:
        scene_meta_list = [_merged_scene_meta(i) for i in range(len(scenes))]

    def _render_scene_clip_ffmpeg(src_path: Path, out_path: Path, *, dur: float, index: int, start_override: float | None = None) -> None:
        dur_s = max(0.8, float(dur or 0.8))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if _is_video(src_path):
            vf = _scene_vf()
            vd = _probe_duration_sec(src_path)
            start = max(0.0, float(start_override or 0.0)) if start_override is not None else 0.0
            if start_override is None and vd > dur_s + 0.4:
                margin = min(1.2, vd * 0.12)
                start_min = max(0.05, margin)
                start_max = max(0.05, vd - dur_s - 0.05)
                start = random.uniform(start_min, start_max) if start_max > start_min else 0.0
            elif start_override is not None and vd > dur_s + 0.1:
                start = min(start, max(0.0, vd - dur_s - 0.02))
            args = [
                "-y", "-ss", f"{start:.3f}", "-t", f"{dur_s:.3f}", "-i", ffmpeg_path(src_path),
                "-an", "-vf", vf, "-r", str(fps), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", ffmpeg_path(out_path),
            ]
            timeout_s = 90
        else:
            vf = _image_motion_vf(scene_meta_list[index] if index < len(scene_meta_list) else {}, dur_s=dur_s, index=index)
            args = [
                "-y", "-loop", "1", "-t", f"{dur_s:.3f}", "-i", ffmpeg_path(src_path),
                "-an", "-vf", vf, "-r", str(fps), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", ffmpeg_path(out_path),
            ]
            timeout_s = 45
        run_ffmpeg(args, timeout_s=timeout_s)

    def _transition_plan() -> list[tuple[str, float]]:
        plan: list[tuple[str, float]] = []
        default_transition = str(transition or "none").strip().lower() or "none"
        default_sec = _clamp(float(transition_sec or 0.0), 0.0, 1.2)
        for index in range(1, len(scenes)):
            kind, seconds = _compute_dynamic_transition(scene_meta_list[index - 1], scene_meta_list[index], default_transition, default_sec)
            max_allowed = max(0.0, min(float(base_durs[index - 1]), float(base_durs[index])) - 0.12)
            seconds = _clamp(float(seconds or 0.0), 0.0, max_allowed)
            if kind != "crossfade" or seconds < 0.02:
                plan.append(("none", 0.0))
            else:
                plan.append(("crossfade", seconds))
        return plan

    def _concat_clip_paths(clip_paths: list[Path], silent_tmp: Path, list_path: Path) -> None:
        concat_lines = []
        for clip_path in clip_paths:
            concat_path = ffmpeg_path(clip_path).replace("'", "''")
            concat_lines.append(f"file '{concat_path}'\n")
        list_path.write_text("".join(concat_lines), encoding="utf-8")
        run_ffmpeg([
            "-y", "-f", "concat", "-safe", "0", "-i", ffmpeg_path(list_path), "-an",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", ffmpeg_path(silent_tmp),
        ], timeout_s=180)

    def _xfade_clip_paths(clip_paths: list[Path], silent_tmp: Path, transitions: list[tuple[str, float]]) -> None:
        args: list[str] = ["-y"]
        for clip_path in clip_paths:
            args.extend(["-i", ffmpeg_path(clip_path)])

        filter_parts: list[str] = []
        for index in range(len(clip_paths)):
            filter_parts.append(f"[{index}:v]settb=AVTB,format=yuv420p[v{index}]")

        current_label = "v0"
        elapsed = float(base_durs[0])
        for index in range(1, len(clip_paths)):
            transition_kind, transition_len = transitions[index - 1]
            fade_len = transition_len if transition_kind == "crossfade" else 0.001
            fade_len = _clamp(float(fade_len), 0.001, max(0.001, min(float(base_durs[index - 1]), float(base_durs[index])) - 0.06))
            offset = max(0.0, elapsed - fade_len)
            next_label = f"x{index}"
            filter_parts.append(
                f"[{current_label}][v{index}]xfade=transition=fade:duration={fade_len:.3f}:offset={offset:.3f}[{next_label}]"
            )
            elapsed = elapsed + float(base_durs[index]) - fade_len
            current_label = next_label

        args.extend([
            "-filter_complex", ";".join(filter_parts),
            "-map", f"[{current_label}]",
            "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", ffmpeg_path(silent_tmp),
        ])
        run_ffmpeg(args, timeout_s=max(180, 120 + len(clip_paths) * 20))

    def _build_silent_video_track_ffmpeg() -> Path:
        total = len(scenes)
        if total <= 0:
            raise RuntimeError("没有可渲染的镜头")
        ts2 = now_utc().strftime("%Y%m%d_%H%M%S")
        clips_dir = out_dir / f"silent_parts_{ts2}"
        list_path = out_dir / f"silent_parts_{ts2}.txt"
        clips_dir.mkdir(parents=True, exist_ok=True)
        clip_paths: list[Path] = []
        for index, _scene in enumerate(scenes):
            wait_if_job_paused(target_job_id)
            if is_job_cancelled(job_id):
                raise RuntimeError("cancelled")
            clip_out = clips_dir / f"part_{index:03d}.mp4"
            start_override, _end_override = clip_plan[index]
            _render_scene_clip_ffmpeg(image_paths[index], clip_out, dur=float(base_durs[index]), index=index, start_override=start_override)
            clip_paths.append(clip_out)
            if index % 2 == 0:
                on_update(progress=min(78, 60 + int((index + 1) / total * 18)), message="渲染视频轨")
        on_update(progress=80, message="写入静音视频")
        silent_tmp = out_dir / f"silent_tmp_{ts2}.mp4"

        if total == 1:
            shutil.copy2(clip_paths[0], silent_tmp)
        else:
            transitions = _transition_plan()
            use_crossfade = any(kind == "crossfade" and seconds >= 0.02 for kind, seconds in transitions)
            if use_crossfade:
                _xfade_clip_paths(clip_paths, silent_tmp, transitions)
            else:
                _concat_clip_paths(clip_paths, silent_tmp, list_path)
        try:
            if silent_path.exists():
                silent_path.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            silent_tmp.replace(silent_path)
        except Exception:
            silent_path_local = silent_tmp
        else:
            silent_path_local = silent_path
        try:
            list_path.unlink(missing_ok=True)
            for clip_path in clip_paths:
                clip_path.unlink(missing_ok=True)
            clips_dir.rmdir()
        except Exception:
            pass
        return silent_path_local

    ffmpeg_track_err = ""
    try:
        return _build_silent_video_track_ffmpeg()
    except Exception as exc:
        ffmpeg_track_err = str(exc).strip()
        if ffmpeg_track_err == "cancelled":
            raise RuntimeError("cancelled") from exc

    raise RuntimeError(f"写入静音视频失败：视频轨生成异常，请稍后重试。{ffmpeg_track_err[:200]}")
