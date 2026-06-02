
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from app.settings import settings


@dataclass(frozen=True)
class CleanupResult:
    cleaned_files: int
    cleaned_bytes: int
    errors: list[str]

    @property
    def cleaned_mb(self) -> float:
        return self.cleaned_bytes / (1024 * 1024)

    @property
    def cleaned_gb(self) -> float:
        return self.cleaned_bytes / (1024 * 1024 * 1024)


def get_file_age_hours(file_path: Path) -> float:
    """Get file age in hours since last modification."""
    try:
        mtime = file_path.stat().st_mtime
        age_seconds = time.time() - mtime
        return age_seconds / 3600
    except Exception:
        return 0.0


def get_file_age_days(file_path: Path) -> float:
    """Get file age in days since last modification."""
    return get_file_age_hours(file_path) / 24


def get_directory_size(directory: Path) -> int:
    """Get total size of all files in a directory in bytes."""
    total_size = 0
    try:
        for item in directory.rglob("*"):
            if item.is_file():
                try:
                    total_size += item.stat().st_size
                except Exception:
                    pass
    except Exception:
        pass
    return total_size


def cleanup_tts_cache(
    max_age_days: int | None = None,
    max_size_gb: float | None = None,
    dry_run: bool = False,
) -> CleanupResult:
    """Clean up TTS cache files.

    Args:
        max_age_days: Maximum age in days for cache files. None uses settings.
        max_size_gb: Maximum total size in GB. None uses settings.
        dry_run: If True, only report what would be deleted without actually deleting.

    Returns:
        CleanupResult with statistics.
    """
    if max_age_days is None:
        max_age_days = settings.tts_cache_max_age_days
    if max_size_gb is None:
        max_size_gb = settings.tts_cache_max_size_gb

    tts_cache_dir = settings.assets_dir / "tts_cache"
    if not tts_cache_dir.exists():
        return CleanupResult(cleaned_files=0, cleaned_bytes=0, errors=[])

    cleaned_files = 0
    cleaned_bytes = 0
    errors: list[str] = []

    max_size_bytes = int(max_size_gb * 1024 * 1024 * 1024)

    files_to_delete: list[tuple[Path, float, int]] = []

    try:
        for item in tts_cache_dir.iterdir():
            if not item.is_file():
                continue
            try:
                age_days = get_file_age_days(item)
                file_size = item.stat().st_size
                files_to_delete.append((item, age_days, file_size))
            except Exception as e:
                errors.append(f"Failed to stat {item.name}: {e}")
    except Exception as e:
        errors.append(f"Failed to list tts_cache directory: {e}")
        return CleanupResult(cleaned_files=0, cleaned_bytes=0, errors=errors)

    files_to_delete.sort(key=lambda x: x[1], reverse=True)

    for file_path, age_days, file_size in files_to_delete:
        should_delete = False

        if age_days > max_age_days:
            should_delete = True
            logger.debug("tts cache file {} is {:.1f} days old max_days={}", file_path.name, age_days, max_age_days)

        if not should_delete:
            current_size = get_directory_size(tts_cache_dir)
            if current_size > max_size_bytes:
                should_delete = True
                logger.debug("tts cache size {:.2f}GB exceeds limit {}GB deleting {}", current_size / (1024**3), max_size_gb, file_path.name)

        if should_delete:
            if dry_run:
                logger.info("[DRY RUN] would delete tts cache file {} ({:.1f}KB, {:.1f} days old)", file_path.name, file_size / 1024, age_days)
                cleaned_files += 1
                cleaned_bytes += file_size
            else:
                try:
                    file_path.unlink()
                    cleaned_files += 1
                    cleaned_bytes += file_size
                    logger.debug("deleted tts cache file {}", file_path.name)
                except Exception as e:
                    errors.append(f"Failed to delete {file_path.name}: {e}")

    return CleanupResult(cleaned_files=cleaned_files, cleaned_bytes=cleaned_bytes, errors=errors)


def cleanup_temp_downloads(
    max_age_hours: int | None = None,
    dry_run: bool = False,
) -> CleanupResult:
    """Clean up temporary download files.

    Args:
        max_age_hours: Maximum age in hours for temp files. None uses settings.
        dry_run: If True, only report what would be deleted without actually deleting.

    Returns:
        CleanupResult with statistics.
    """
    if max_age_hours is None:
        max_age_hours = settings.temp_file_max_age_hours

    temp_dir = settings.assets_dir / "library" / "_tmp"
    if not temp_dir.exists():
        return CleanupResult(cleaned_files=0, cleaned_bytes=0, errors=[])

    cleaned_files = 0
    cleaned_bytes = 0
    errors: list[str] = []

    try:
        for item in temp_dir.iterdir():
            if not item.is_file():
                continue
            try:
                age_hours = get_file_age_hours(item)
                if age_hours > max_age_hours:
                    file_size = item.stat().st_size
                    if dry_run:
                        logger.info("[DRY RUN] would delete temp file {} ({:.1f}KB, {:.1f} hours old)", item.name, file_size / 1024, age_hours)
                        cleaned_files += 1
                        cleaned_bytes += file_size
                    else:
                        item.unlink()
                        cleaned_files += 1
                        cleaned_bytes += file_size
                        logger.debug("deleted temp file {}", item.name)
            except Exception as e:
                errors.append(f"Failed to process {item.name}: {e}")
    except Exception as e:
        errors.append(f"Failed to list _tmp directory: {e}")

    return CleanupResult(cleaned_files=cleaned_files, cleaned_bytes=cleaned_bytes, errors=errors)


def cleanup_project_subtitles(
    project_id: int,
    keep_latest: int = 1,
    dry_run: bool = False,
) -> CleanupResult:
    """Clean up old subtitle files for a project.

    Args:
        project_id: Project ID.
        keep_latest: Number of latest subtitle files to keep.
        dry_run: If True, only report what would be deleted without actually deleting.

    Returns:
        CleanupResult with statistics.
    """
    subtitle_dir = settings.assets_dir / "subtitles" / f"project_{project_id}"
    if not subtitle_dir.exists():
        return CleanupResult(cleaned_files=0, cleaned_bytes=0, errors=[])

    cleaned_files = 0
    cleaned_bytes = 0
    errors: list[str] = []

    srt_files: list[tuple[Path, float, int]] = []
    ass_files: list[tuple[Path, float, int]] = []

    try:
        for item in subtitle_dir.iterdir():
            if not item.is_file():
                continue
            try:
                mtime = item.stat().st_mtime
                file_size = item.stat().st_size
                if item.suffix.lower() == ".srt":
                    srt_files.append((item, mtime, file_size))
                elif item.suffix.lower() == ".ass":
                    ass_files.append((item, mtime, file_size))
            except Exception as e:
                errors.append(f"Failed to stat {item.name}: {e}")
    except Exception as e:
        errors.append(f"Failed to list subtitle directory: {e}")
        return CleanupResult(cleaned_files=0, cleaned_bytes=0, errors=errors)

    srt_files.sort(key=lambda x: x[1], reverse=True)
    ass_files.sort(key=lambda x: x[1], reverse=True)

    for files_list in [srt_files, ass_files]:
        for i, (file_path, mtime, file_size) in enumerate(files_list):
            if i >= keep_latest:
                if dry_run:
                    logger.info("[DRY RUN] would delete subtitle file {}", file_path.name)
                    cleaned_files += 1
                    cleaned_bytes += file_size
                else:
                    try:
                        file_path.unlink()
                        cleaned_files += 1
                        cleaned_bytes += file_size
                        logger.debug("deleted subtitle file {}", file_path.name)
                    except Exception as e:
                        errors.append(f"Failed to delete {file_path.name}: {e}")

    return CleanupResult(cleaned_files=cleaned_files, cleaned_bytes=cleaned_bytes, errors=errors)


def cleanup_project_temp_videos(
    project_id: int,
    dry_run: bool = False,
) -> CleanupResult:
    """Clean up temporary video files for a project.

    Args:
        project_id: Project ID.
        dry_run: If True, only report what would be deleted without actually deleting.

    Returns:
        CleanupResult with statistics.
    """
    export_dir = settings.exports_dir / f"project_{project_id}"
    if not export_dir.exists():
        return CleanupResult(cleaned_files=0, cleaned_bytes=0, errors=[])

    cleaned_files = 0
    cleaned_bytes = 0
    errors: list[str] = []

    try:
        for item in export_dir.iterdir():
            if not item.is_file():
                continue
            name_lower = item.name.lower()
            if "_tmp_" in name_lower or name_lower.endswith(".tmp"):
                try:
                    file_size = item.stat().st_size
                    if dry_run:
                        logger.info("[DRY RUN] would delete temp video {}", item.name)
                        cleaned_files += 1
                        cleaned_bytes += file_size
                    else:
                        item.unlink()
                        cleaned_files += 1
                        cleaned_bytes += file_size
                        logger.debug("deleted temp video {}", item.name)
                except Exception as e:
                    errors.append(f"Failed to delete {item.name}: {e}")
    except Exception as e:
        errors.append(f"Failed to list export directory: {e}")

    return CleanupResult(cleaned_files=cleaned_files, cleaned_bytes=cleaned_bytes, errors=errors)


def cleanup_orphan_files(
    dry_run: bool = False,
) -> CleanupResult:
    """Clean up orphan files that are no longer associated with any project.

    This is a more aggressive cleanup that should be used with caution.

    Args:
        dry_run: If True, only report what would be deleted without actually deleting.

    Returns:
        CleanupResult with statistics.
    """
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import Asset, Project

    cleaned_files = 0
    cleaned_bytes = 0
    errors: list[str] = []

    try:
        with Session(engine) as session:
            active_project_ids = set(p.id for p in session.exec(select(Project.id)).all())
            active_asset_paths = set(
                str(a.rel_path).lstrip("/") for a in session.exec(select(Asset.rel_path)).all() if a.rel_path
            )
    except Exception as e:
        errors.append(f"Failed to get active projects/assets: {e}")
        return CleanupResult(cleaned_files=0, cleaned_bytes=0, errors=errors)

    return CleanupResult(cleaned_files=cleaned_files, cleaned_bytes=cleaned_bytes, errors=errors)


def run_full_cleanup(dry_run: bool = False) -> dict:
    """Run all cleanup tasks.

    Args:
        dry_run: If True, only report what would be deleted without actually deleting.

    Returns:
        Dictionary with cleanup results.
    """
    results = {}

    logger.info("starting full cleanup dry_run={}", dry_run)

    tts_result = cleanup_tts_cache(dry_run=dry_run)
    results["tts_cache"] = {
        "cleaned_files": tts_result.cleaned_files,
        "cleaned_mb": tts_result.cleaned_mb,
        "errors": tts_result.errors,
    }

    temp_result = cleanup_temp_downloads(dry_run=dry_run)
    results["temp_downloads"] = {
        "cleaned_files": temp_result.cleaned_files,
        "cleaned_mb": temp_result.cleaned_mb,
        "errors": temp_result.errors,
    }

    orphan_result = cleanup_orphan_files(dry_run=dry_run)
    results["orphan_files"] = {
        "cleaned_files": orphan_result.cleaned_files,
        "cleaned_mb": orphan_result.cleaned_mb,
        "errors": orphan_result.errors,
    }

    total_files = tts_result.cleaned_files + temp_result.cleaned_files + orphan_result.cleaned_files
    total_bytes = tts_result.cleaned_bytes + temp_result.cleaned_bytes + orphan_result.cleaned_bytes
    total_errors = tts_result.errors + temp_result.errors + orphan_result.errors

    results["summary"] = {
        "total_files": total_files,
        "total_mb": total_bytes / (1024 * 1024),
        "total_gb": total_bytes / (1024 * 1024 * 1024),
        "total_errors": len(total_errors),
    }

    logger.info("full cleanup complete files={} size_mb={:.2f} errors={}", total_files, total_bytes / (1024 * 1024), len(total_errors))

    return results


def get_disk_usage() -> dict:
    """Get disk usage statistics for the data directory.

    Returns:
        Dictionary with disk usage information.
    """
    data_dir = settings.data_dir

    try:
        total, used, free = shutil.disk_usage(data_dir)
    except Exception:
        total, used, free = 0, 0, 0

    tts_cache_dir = settings.assets_dir / "tts_cache"
    tts_cache_size = get_directory_size(tts_cache_dir) if tts_cache_dir.exists() else 0

    temp_dir = settings.assets_dir / "library" / "_tmp"
    temp_size = get_directory_size(temp_dir) if temp_dir.exists() else 0

    exports_dir = settings.exports_dir
    exports_size = get_directory_size(exports_dir) if exports_dir.exists() else 0

    assets_dir = settings.assets_dir
    assets_size = get_directory_size(assets_dir) if assets_dir.exists() else 0

    return {
        "disk_total_gb": total / (1024**3),
        "disk_used_gb": used / (1024**3),
        "disk_free_gb": free / (1024**3),
        "disk_used_percent": (used / total * 100) if total > 0 else 0,
        "tts_cache_mb": tts_cache_size / (1024**2),
        "temp_files_mb": temp_size / (1024**2),
        "exports_gb": exports_size / (1024**3),
        "assets_gb": assets_size / (1024**3),
    }
