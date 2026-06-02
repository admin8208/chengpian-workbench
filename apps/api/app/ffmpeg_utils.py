
import subprocess
from pathlib import Path

import imageio_ffmpeg


def ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def run_ffmpeg(args: list[str], *, timeout_s: int | None = None) -> None:
    exe = ffmpeg_exe()
    cmd = [exe, *args]
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=(None if timeout_s is None else max(1, int(timeout_s))),
        )
    except subprocess.TimeoutExpired as e:
        err = str(getattr(e, "stderr", "") or "").strip()
        out = str(getattr(e, "stdout", "") or "").strip()
        msg = err or out or "ffmpeg timed out"
        if len(msg) > 1200:
            msg = msg[:1200] + "..."
        raise RuntimeError(f"Command '{cmd}' timed out after {int(timeout_s or 0)}s.\n{msg}") from e
    if p.returncode != 0:
        msg = (p.stderr or "").strip() or (p.stdout or "").strip() or f"ffmpeg failed ({p.returncode})"
        if len(msg) > 1200:
            msg = msg[:1200] + "..."
        raise RuntimeError(f"Command '{cmd}' returned non-zero exit status {p.returncode}.\n{msg}")


def ffmpeg_path(p: Path) -> str:
    # Use forward slashes. For Windows drive letters, ffmpeg prefers C:/...
    s = str(p.resolve()).replace("\\", "/")
    return s
