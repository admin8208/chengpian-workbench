
import json
import mimetypes
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests
from sqlmodel import select

from app.db import session_scope
from app.ffmpeg_utils import ffmpeg_path, run_ffmpeg
from app.models import Asset
from app.project_paths import project_imported_dir, rel_to_projects_root
from app.settings import settings
from app.modules.media.wikimedia import url_hash
from app.http_client import new_session
from app.time_utils import utc_iso_z


@dataclass(frozen=True)
class ImportRequest:
    provider: str
    kind: str  # image|video|audio
    title: str
    page_url: str
    file_url: str
    width: int | None = None
    height: int | None = None
    duration_sec: float | None = None
    thumb_url: str | None = None
    preview_url: str | None = None
    license_short: str = ""
    license_url: str | None = None
    author: str = ""
    attribution: str = ""


def _download_with_limit(*, url: str, target: Path, max_bytes: int, connect_timeout_s: int = 20, read_timeout_s: int = 120, headers: dict[str, str] | None = None) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    s = new_session(headers=headers or None)
    with s.get(url, stream=True, timeout=(max(3, int(connect_timeout_s or 20)), max(10, int(read_timeout_s or 120)))) as r:
        if not r.ok:
            raise RuntimeError(f"download failed: {r.status_code}")
        total = 0
        with open(target, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise RuntimeError("file too large")
                f.write(chunk)


def import_to_library(
    req: ImportRequest,
    *,
    max_bytes_override: int | None = None,
    connect_timeout_s: int = 20,
    read_timeout_s: int = 120,
    source_headers: dict[str, str] | None = None,
    project_id: int | None = None,
    tag: str = "library",
) -> Asset:
    provider = (req.provider or "").strip().lower()
    kind = (req.kind or "").strip().lower()
    if provider not in ("wikimedia", "pexels", "pixabay", "douyin"):
        raise ValueError("unsupported provider")
    if kind not in ("image", "video", "audio"):
        raise ValueError("invalid kind")
    file_url = (req.file_url or "").strip()
    page_url = (req.page_url or "").strip()
    if not file_url or not page_url:
        raise ValueError("missing file_url/page_url")

    h = url_hash(file_url)
    if not h:
        raise ValueError("invalid file_url")

    lib_dir = settings.assets_dir / "library" / kind
    tmp_dir = settings.assets_dir / "library" / "_tmp"
    lib_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # Determine final extension and download size limits
    if kind == "image":
        ext = ".jpg"
        u = file_url.split("?")[0].lower()
        for e in (".png", ".jpg", ".jpeg", ".webp"):
            if u.endswith(e):
                ext = ".jpg" if e == ".jpeg" else e
                break
        max_bytes = 12 * 1024 * 1024
        final_path = lib_dir / f"img_{h}{ext}"
    elif kind == "video":
        # Normalize to mp4
        max_bytes = 200 * 1024 * 1024
        final_path = lib_dir / f"vid_{h}.mp4"
    else:
        # audio: normalize to mp3
        max_bytes = 80 * 1024 * 1024
        final_path = lib_dir / f"aud_{h}.mp3"

    rel = str(final_path.resolve().relative_to(settings.assets_dir)).replace("\\", "/")

    asset_tag = str(tag or "library").strip() or "library"

    with session_scope() as session:
        q = select(Asset).where(Asset.tag == asset_tag).where(Asset.rel_path == rel)
        if project_id is None:
            q = q.where(Asset.project_id == None)  # noqa: E711
        else:
            q = q.where(Asset.project_id == int(project_id))
        existing = session.exec(q).first()
        if existing and existing.id is not None:
            return existing

    # Download to temp first
    tmp_path = tmp_dir / f"dl_{h}.bin"
    if max_bytes_override is not None:
        try:
            max_bytes = max(1024 * 1024, int(max_bytes_override))
        except Exception:
            pass
    _download_with_limit(
        url=file_url,
        target=tmp_path,
        max_bytes=max_bytes,
        connect_timeout_s=connect_timeout_s,
        read_timeout_s=read_timeout_s,
        headers=source_headers,
    )

    # Transcode if needed
    if kind == "video":
        out_tmp = tmp_dir / f"out_{h}.mp4"
        run_ffmpeg(
            [
                "-y",
                "-i",
                ffmpeg_path(tmp_path),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                ffmpeg_path(out_tmp),
            ],
            timeout_s=180,
        )
        tmp_path = out_tmp
    elif kind == "audio":
        out_tmp = tmp_dir / f"out_{h}.mp3"
        run_ffmpeg(
            [
                "-y",
                "-i",
                ffmpeg_path(tmp_path),
                "-vn",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "192k",
                ffmpeg_path(out_tmp),
            ],
            timeout_s=120,
        )
        tmp_path = out_tmp

    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(tmp_path), str(final_path))
    except Exception:
        # Best-effort: if move fails, try copy
        shutil.copyfile(str(tmp_path), str(final_path))

    mime = mimetypes.guess_type(str(final_path))[0] or ""
    meta = {
        "provider": provider,
        "kind": kind,
        "title": req.title,
        "page_url": page_url,
        "file_url": file_url,
        "width": req.width,
        "height": req.height,
        "duration_sec": req.duration_sec,
        "thumb_url": req.thumb_url,
        "preview_url": req.preview_url,
        "license_short": req.license_short,
        "license_url": req.license_url,
        "author": req.author,
        "attribution": req.attribution,
        "imported_at": utc_iso_z(),
    }

    with session_scope() as session:
        a = Asset(
            kind=kind,
            rel_path=rel,
            mime=mime,
            project_id=(int(project_id) if project_id is not None else None),
            scene_id=None,
            tag=asset_tag,
            meta_json=json.dumps(meta, ensure_ascii=True),
        )
        session.add(a)
        session.flush()
        session.refresh(a)
        return a


def import_to_project(
    req: ImportRequest,
    *,
    project_id: int,
    max_bytes_override: int | None = None,
    connect_timeout_s: int = 20,
    read_timeout_s: int = 120,
    source_headers: dict[str, str] | None = None,
    tag: str = "project_source",
) -> Asset:
    provider = (req.provider or "").strip().lower()
    kind = (req.kind or "").strip().lower()
    if provider not in ("wikimedia", "pexels", "pixabay", "douyin"):
        raise ValueError("unsupported provider")
    if kind not in ("image", "video", "audio"):
        raise ValueError("invalid kind")
    file_url = (req.file_url or "").strip()
    page_url = (req.page_url or "").strip()
    if not file_url or not page_url:
        raise ValueError("missing file_url/page_url")

    pid = int(project_id)
    if pid <= 0:
        raise ValueError("invalid project_id")

    h = url_hash(file_url)
    if not h:
        raise ValueError("invalid file_url")

    imports_root = project_imported_dir(pid)
    target_dir = imports_root / kind
    tmp_dir = imports_root / "_tmp"
    target_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    if kind == "image":
        ext = ".jpg"
        u = file_url.split("?")[0].lower()
        for e in (".png", ".jpg", ".jpeg", ".webp"):
            if u.endswith(e):
                ext = ".jpg" if e == ".jpeg" else e
                break
        max_bytes = 12 * 1024 * 1024
        final_path = target_dir / f"img_{h}{ext}"
    elif kind == "video":
        max_bytes = 200 * 1024 * 1024
        final_path = target_dir / f"vid_{h}.mp4"
    else:
        max_bytes = 80 * 1024 * 1024
        final_path = target_dir / f"aud_{h}.mp3"

    rel = rel_to_projects_root(final_path)
    asset_tag = str(tag or "project_source").strip() or "project_source"

    with session_scope() as session:
        q = (
            select(Asset)
            .where(Asset.tag == asset_tag)
            .where(Asset.rel_path == rel)
            .where(Asset.project_id == pid)
        )
        existing = session.exec(q).first()
        if existing and existing.id is not None:
            return existing

    tmp_path = tmp_dir / f"dl_{h}.bin"
    if max_bytes_override is not None:
        try:
            max_bytes = max(1024 * 1024, int(max_bytes_override))
        except Exception:
            pass
    _download_with_limit(
        url=file_url,
        target=tmp_path,
        max_bytes=max_bytes,
        connect_timeout_s=connect_timeout_s,
        read_timeout_s=read_timeout_s,
        headers=source_headers,
    )

    if kind == "video":
        out_tmp = tmp_dir / f"out_{h}.mp4"
        run_ffmpeg(
            [
                "-y",
                "-i",
                ffmpeg_path(tmp_path),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                ffmpeg_path(out_tmp),
            ],
            timeout_s=180,
        )
        tmp_path = out_tmp
    elif kind == "audio":
        out_tmp = tmp_dir / f"out_{h}.mp3"
        run_ffmpeg(
            [
                "-y",
                "-i",
                ffmpeg_path(tmp_path),
                "-vn",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "192k",
                ffmpeg_path(out_tmp),
            ],
            timeout_s=120,
        )
        tmp_path = out_tmp

    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(tmp_path), str(final_path))
    except Exception:
        shutil.copyfile(str(tmp_path), str(final_path))

    mime = mimetypes.guess_type(str(final_path))[0] or ""
    meta = {
        "provider": provider,
        "kind": kind,
        "title": req.title,
        "page_url": page_url,
        "file_url": file_url,
        "width": req.width,
        "height": req.height,
        "duration_sec": req.duration_sec,
        "thumb_url": req.thumb_url,
        "preview_url": req.preview_url,
        "license_short": req.license_short,
        "license_url": req.license_url,
        "author": req.author,
        "attribution": req.attribution,
        "imported_at": utc_iso_z(),
        "import_scope": "project",
    }

    with session_scope() as session:
        a = Asset(
            kind=kind,
            rel_path=rel,
            mime=mime,
            project_id=pid,
            scene_id=None,
            tag=asset_tag,
            meta_json=json.dumps(meta, ensure_ascii=True),
        )
        session.add(a)
        session.flush()
        session.refresh(a)
        return a
