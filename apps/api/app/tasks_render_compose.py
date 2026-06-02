from dataclasses import dataclass
from pathlib import Path

from app.ffmpeg_utils import ffmpeg_path


@dataclass
class RenderOutputPaths:
    out_video_dir: Path
    out_file: Path
    out_tmp: Path


@dataclass
class RenderMuxPlan:
    args: list[str]


def build_output_paths(*, out_dir: Path, export_tag: str, ts: str) -> RenderOutputPaths:
    tag = str(export_tag or "export").strip().lower()
    out_video_dir = out_dir
    out_file = out_dir / "final.mp4"
    out_tmp = out_dir / f"final_tmp_{ts}.mp4"
    if tag == "export":
        out_video_dir = out_dir
        out_file = out_video_dir / "final.mp4"
        out_tmp = out_video_dir / f"final_tmp_{ts}.mp4"
    else:
        safe_tag = "".join([ch for ch in tag if ch.isalnum() or ch in ("-", "_", ".")]).strip("_") or "video"
        out_file = out_dir / f"{safe_tag}_{ts}.mp4"
        out_tmp = out_dir / f"{safe_tag}_tmp_{ts}.mp4"
    return RenderOutputPaths(out_video_dir=out_video_dir, out_file=out_file, out_tmp=out_tmp)


def build_mux_plan(
    *,
    silent_path: Path,
    audio_path: Path,
    out_tmp: Path,
    voice_volume: float,
    vf: str | None,
) -> RenderMuxPlan:
    args: list[str] = ["-y", "-i", ffmpeg_path(silent_path), "-i", ffmpeg_path(audio_path)]
    filter_complex = f"[1:a]volume={voice_volume}[a]"

    args += ["-filter_complex", filter_complex]
    color_filters = "eq=saturation=1.1:contrast=1.05:brightness=0.02"
    enhanced_vf = f"{color_filters},{vf}" if vf else color_filters
    args += ["-vf", enhanced_vf]
    args += [
        "-map", "0:v:0", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", ffmpeg_path(out_tmp),
    ]
    return RenderMuxPlan(
        args=args,
    )


def extend_mux_meta(
    *,
    mux_meta: dict | None,
    target_w: int,
    target_h: int,
    aspect: str,
    transition: str,
    transition_sec: float,
    motion_zoom: float,
    subtitle_style: str,
) -> dict:
    meta = mux_meta if isinstance(mux_meta, dict) else {}
    meta.update(
        {
            "width": int(target_w),
            "height": int(target_h),
            "aspect": str(aspect),
            "transition": str(transition),
            "transition_sec": float(transition_sec),
            "motion_zoom": float(motion_zoom),
            "subtitle_style": str(subtitle_style),
        }
    )
    return meta
