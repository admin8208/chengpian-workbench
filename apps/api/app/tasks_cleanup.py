"""Scheduled cleanup task - extracted from tasks.py"""
from __future__ import annotations

from loguru import logger
from huey import crontab

from app.huey_app import huey
from app.logging_setup import sanitize_log_text
from app.cleanup_utils import (
    cleanup_orphan_files,
    cleanup_temp_downloads,
    cleanup_tts_cache,
)


@huey.periodic_task(crontab(minute="0", hour="*/6"))
def scheduled_cleanup_task() -> None:
    """Periodic cleanup of temporary files and caches."""
    try:
        results = [
            cleanup_tts_cache(),
            cleanup_temp_downloads(),
            cleanup_orphan_files(),
        ]
        cleaned_files = sum(int(getattr(item, "cleaned_files", 0) or 0) for item in results)
        cleaned_bytes = sum(int(getattr(item, "cleaned_bytes", 0) or 0) for item in results)
        errors = []
        for item in results:
            errors.extend(list(getattr(item, "errors", []) or []))
        logger.info(
            f"scheduled cleanup finished: {cleaned_files} files, {cleaned_bytes / (1024 * 1024):.2f}MB freed, {len(errors)} errors"
        )
        if errors:
            logger.warning("scheduled cleanup errors: {}", "; ".join(sanitize_log_text(item) for item in errors[:5]))

    except Exception as e:
        logger.exception("scheduled cleanup failed: {}", sanitize_log_text(e))
