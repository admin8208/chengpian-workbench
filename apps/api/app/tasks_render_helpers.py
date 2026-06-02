from pathlib import Path

from app.ffmpeg_utils import ffmpeg_path, run_ffmpeg
from app.subtitles import subtitle_force_style


FFMPEG_MUX_TIMEOUT_S = 240


def is_generated_render_rel_path(pid: int, rel_path: str | None) -> bool:
    rel = str(rel_path or "").replace("\\", "/").lstrip("/")
    if not rel:
        return False
    audio_prefix = f"audio/project_{int(pid)}/"
    subtitle_prefix = f"subtitles/project_{int(pid)}/"
    if rel.startswith(audio_prefix):
        name = rel[len(audio_prefix) :]
        return name == "voice.mp3" or (name.startswith("voice_") and not name.startswith("voice_upload_"))
    if rel.startswith(subtitle_prefix):
        name = rel[len(subtitle_prefix) :]
        return name == "subtitle.srt" or (name.startswith("subtitle_") and not name.startswith("subtitle_upload_"))
    return False


def prepare_subtitle_filters(srt_path: Path, *, subtitle_style: str, subtitle_overrides: dict, aspect: str = "landscape") -> tuple[str | None, str | None]:
    vf = None
    vf_retry = None
    if not srt_path.exists() or srt_path.stat().st_size <= 0:
        return (vf, vf_retry)
    sub_path = srt_path
    style = subtitle_force_style(subtitle_style, subtitle_overrides, aspect=aspect)

    sub_f = ffmpeg_path(sub_path)
    try:
        if len(sub_f) >= 3 and sub_f[1:3] == ":/" and sub_f[0].isalpha():
            sub_f = sub_f.replace(":", "\\:", 1)
        sub_f = sub_f.replace("'", "\\'")
    except Exception:
        pass

    if sub_path.suffix.lower() == ".ass":
        vf = f"subtitles=filename='{sub_f}':force_style='{style}'"
        srt_f = ffmpeg_path(srt_path)
        try:
            if len(srt_f) >= 3 and srt_f[1:3] == ":/" and srt_f[0].isalpha():
                srt_f = srt_f.replace(":", "\\:", 1)
            srt_f = srt_f.replace("'", "\\'")
            vf_retry = f"subtitles=filename='{srt_f}':force_style='{style}'"
        except Exception:
            vf_retry = None
    else:
        vf = f"subtitles=filename='{sub_f}':force_style='{style}'"
    return (vf, vf_retry)


def run_ffmpeg_mux_with_fallback(args: list[str], *, vf: str | None, vf_retry: str | None, on_update) -> dict:
    try:
        run_ffmpeg(args, timeout_s=FFMPEG_MUX_TIMEOUT_S)
        return {
            "subtitle_mode": ("burned" if vf else "none"),
            "subtitle_degraded": False,
            "subtitle_retry_used": False,
        }
    except Exception as exc:
        if vf_retry and vf_retry != vf:
            try:
                retry_args = list(args)
                vf_idx = retry_args.index("-vf")
                retry_args[vf_idx + 1] = vf_retry
                on_update(progress=88, message="字幕烧录重试：切换稳定字幕路径")
                run_ffmpeg(retry_args, timeout_s=FFMPEG_MUX_TIMEOUT_S)
                return {
                    "subtitle_mode": "burned_retry",
                    "subtitle_degraded": False,
                    "subtitle_retry_used": True,
                }
            except Exception as retry_exc:
                raise RuntimeError(f"字幕烧录失败：{retry_exc}") from retry_exc
        if vf:
            raise RuntimeError(f"字幕烧录失败：{exc}") from exc
        raise RuntimeError(f"ffmpeg 处理失败：{exc}") from exc
