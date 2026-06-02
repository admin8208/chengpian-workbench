from __future__ import annotations

import json
from pathlib import Path

import imageio_ffmpeg

from app.network_checks import tts_proxy_summary
from app.settings import settings
from app.storage_bootstrap import ensure_runtime_storage


def web_dist_status() -> dict:
    dist = settings.web_dist_dir
    idx = dist / "index.html"
    meta = dist / "build-meta.json"
    src_dir = dist.parent / "src"
    status = {
        "dist_dir": dist,
        "index_exists": idx.exists(),
        "meta_exists": meta.exists(),
        "meta": None,
        "stale": False,
        "src_mtime": None,
        "dist_mtime": None,
        "warnings": [],
    }
    if meta.exists():
        try:
            status["meta"] = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            status["warnings"].append(f"frontend build meta unreadable: {meta}")
    else:
        status["warnings"].append(f"frontend build meta missing: {meta}")

    try:
        dist_mtime = idx.stat().st_mtime if idx.exists() else None
        status["dist_mtime"] = dist_mtime
    except Exception:
        dist_mtime = None

    latest_src_mtime = None
    try:
        if src_dir.exists():
            for p in src_dir.rglob("*"):
                if not p.is_file():
                    continue
                ts = p.stat().st_mtime
                if latest_src_mtime is None or ts > latest_src_mtime:
                    latest_src_mtime = ts
        status["src_mtime"] = latest_src_mtime
    except Exception:
        latest_src_mtime = None

    if latest_src_mtime and dist_mtime and latest_src_mtime > dist_mtime:
        status["stale"] = True
        status["warnings"].append(
            f"frontend dist appears stale: src is newer than dist ({src_dir} > {idx})"
        )
    return status


def run_preflight(*, require_web_dist: bool = False, role: str = "api") -> list[str]:
    notes: list[str] = []
    ensure_runtime_storage()
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    notes.append(f"[{role}] ffmpeg={ffmpeg_exe}")
    notes.append(f"[{role}] database=postgresql")
    notes.append(f"[{role}] data_dir={settings.data_dir}")
    if require_web_dist:
        web = web_dist_status()
        idx = settings.web_dist_dir / "index.html"
        if not web["index_exists"]:
            raise RuntimeError(f"frontend build missing: {idx}")
        if web.get("stale"):
            stale_message = next(
                (warning for warning in (web.get("warnings") or []) if "frontend dist appears stale" in str(warning)),
                f"frontend dist appears stale: {settings.web_dist_dir}",
            )
            raise RuntimeError(stale_message)
        notes.append(f"[{role}] web_dist={settings.web_dist_dir}")
        meta = web.get("meta") or {}
        built_at = str(meta.get("built_at") or "").strip() or "unknown"
        commit = str(meta.get("git_commit") or "").strip() or "unknown"
        notes.append(f"[{role}] web_build={built_at} commit={commit}")
        for warning in web.get("warnings") or []:
            notes.append(f"[{role}] WARN {warning}")
    proxy = tts_proxy_summary()
    if proxy["proxy_detected"]:
        notes.append(f"[{role}] tts_proxy={proxy['proxy']}")
    else:
        notes.append(f"[{role}] tts_proxy=none")
    return notes
