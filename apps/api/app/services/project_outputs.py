import os

from sqlmodel import Session, select

from app.db import session_scope
from app.file_access import signed_file_url
from app.models import Asset
from app.project_paths import asset_disk_path, project_exports_dir, project_path_from_rel, rel_to_projects_root
from app.settings import settings


def stable_final_export_status(project_id: int) -> dict:
    pid = int(project_id)
    with session_scope() as session:
        return resolve_final_export_status(session, pid)


def resolve_final_export_status(session: Session, project_id: int) -> dict:
    pid = int(project_id)
    expected_rel = f"project_{pid}/exports/final.mp4"
    project_url = signed_file_url("projects", expected_rel)
    expected_file = project_path_from_rel(expected_rel)
    export_asset = session.exec(
        select(Asset)
        .where(Asset.project_id == pid)
        .where(Asset.kind == "video")
        .where(Asset.tag == "export")
        .order_by(Asset.created_at.desc())
    ).first()
    if not export_asset:
        try:
            if expected_file.exists() and expected_file.is_file() and expected_file.stat().st_size > 0:
                return {"exists": True, "url": project_url, "size": int(expected_file.stat().st_size)}
        except Exception:
            pass
        return {"exists": False, "url": project_url, "size": 0}

    rel = str(getattr(export_asset, "rel_path", "") or "").strip().lstrip("/")
    path = expected_file
    url = project_url
    exists = False
    size = 0
    try:
        exists = path.exists() and path.is_file() and path.stat().st_size > 0
        size = int(path.stat().st_size) if exists else 0
    except Exception:
        exists = False
        size = 0
    if exists:
        try:
            actual_rel = rel_to_projects_root(path)
            if actual_rel != expected_rel:
                exists = False
                size = 0
        except Exception:
            exists = False
            size = 0
    if exists:
        return {"exists": True, "url": url, "size": size}

    # If an export asset record exists but its rel_path does not match the
    # canonical final path for this project, treat it as invalid instead of
    # falling back to a mismatched project path.
    if rel and rel != expected_rel:
        return {"exists": False, "url": url, "size": 0}

    if rel:
        try:
            asset_path = project_path_from_rel(rel)
            exists = asset_path.exists() and asset_path.is_file() and asset_path.stat().st_size > 0
            size = int(asset_path.stat().st_size) if exists else 0
        except Exception:
            exists = False
            size = 0
        if exists:
            return {"exists": True, "url": signed_file_url("projects", rel), "size": size}
    return {"exists": False, "url": url, "size": 0}


def _int_env(name: str, default: int, lo: int, hi: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except Exception:
        value = default
    return max(lo, min(hi, value))


def cleanup_project_intermediate_artifacts(project_id: int) -> dict:
    """Prune intermediate files/assets and keep storage lean."""
    pid = int(project_id)
    keep_history = _int_env("CHENGPIAN_KEEP_EXPORT_HISTORY", 1, 0, 200)
    keep_generated_tts = _int_env("CHENGPIAN_KEEP_GENERATED_TTS", 1, 0, 50)
    removed_db = 0
    removed_files = 0

    def _drop_asset_file(asset: Asset) -> bool:
        rel = str(getattr(asset, "rel_path", "") or "").strip()
        if not rel:
            return False
        path = asset_disk_path(rel, is_export=bool(str(asset.kind or "") == "video" and str(asset.tag or "") in ("export", "export_history")))
        try:
            if path.exists() and path.is_file():
                path.unlink(missing_ok=True)
                return True
        except Exception:
            return False
        return False

    with session_scope() as session:
        for tag, keep in (("export_history", keep_history),):
            rows = session.exec(
                select(Asset)
                .where(Asset.project_id == pid)
                .where(Asset.kind == "video")
                .where(Asset.tag == tag)
                .order_by(Asset.created_at.desc())
            ).all()
            for old in rows[keep:]:
                try:
                    if _drop_asset_file(old):
                        removed_files += 1
                    session.delete(old)
                    removed_db += 1
                except Exception:
                    pass

        for tag in ("voice_generated", "subtitle_generated"):
            rows = session.exec(
                select(Asset)
                .where(Asset.project_id == pid)
                .where(Asset.tag == tag)
                .order_by(Asset.created_at.desc())
            ).all()
            for old in rows[keep_generated_tts:]:
                try:
                    if _drop_asset_file(old):
                        removed_files += 1
                    session.delete(old)
                    removed_db += 1
                except Exception:
                    pass

    try:
        out_dir = project_exports_dir(pid)
        if out_dir.exists():
            for path in out_dir.glob("*_tmp_*.mp4"):
                try:
                    path.unlink(missing_ok=True)
                    removed_files += 1
                except Exception:
                    pass
    except Exception:
        pass

    try:
        audio_dir = (settings.data_dir / "projects" / f"project_{pid}" / "audio").resolve()
        if audio_dir.exists():
            for path in audio_dir.glob("voice_j*.mp3"):
                try:
                    path.unlink(missing_ok=True)
                    removed_files += 1
                except Exception:
                    pass
        subtitle_dir = (settings.data_dir / "projects" / f"project_{pid}" / "subtitles").resolve()
        if subtitle_dir.exists():
            for path in subtitle_dir.glob("subtitle_j*.srt"):
                try:
                    path.unlink(missing_ok=True)
                    removed_files += 1
                except Exception:
                    pass
    except Exception:
        pass

    return {
        "removed_db": int(removed_db),
        "removed_files": int(removed_files),
        "keep_history": int(keep_history),
        "keep_generated_tts": int(keep_generated_tts),
    }
