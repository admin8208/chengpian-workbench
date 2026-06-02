"""TTS offline install tasks - extracted from tasks.py"""
from __future__ import annotations

from loguru import logger

from app.huey_app import huey
from app.jobs import abort_if_job_cancelled, update_job, wait_if_job_paused
from app.logging_setup import sanitize_log_text
from app.modules.tts.offline import (
    install_all_compatible_offline_voices,
    install_piper_voice,
)


@huey.task()
def tts_offline_install(job_id: int, voice_id: str = "") -> None:
    """Install a single TTS offline voice."""
    if abort_if_job_cancelled(job_id):
        return
    update_job(job_id, status="running", progress=10, message=f"Installing voice: {voice_id}")
    wait_if_job_paused(job_id)
    
    try:
        if not voice_id:
            update_job(job_id, status="failed", progress=100, message="Voice ID required")
            return
        
        install_piper_voice(voice_id=voice_id)
        update_job(job_id, status="done", progress=100, message=f"Voice installed: {voice_id}")

    except Exception as e:
        logger.exception("tts_offline_install failed voice_id={} error={}", voice_id, sanitize_log_text(e))
        update_job(job_id, status="failed", progress=100,
                  message=f"Install failed: {str(e)[:200]}")


@huey.task()
def tts_offline_install_all_compatible(job_id: int) -> None:
    """Install all compatible TTS offline voices."""
    if abort_if_job_cancelled(job_id):
        return
    update_job(job_id, status="running", progress=10, message="Installing all compatible voices...")
    wait_if_job_paused(job_id)
    
    try:
        result = install_all_compatible_offline_voices()
        installed = list(result.get("installed_voice_ids") or [])
        failed = list(result.get("failed") or [])
        if failed:
            update_job(job_id, status="failed", progress=100, message=f"Install finished with failures: installed {len(installed)} voices, failed {len(failed)}")
            return
        update_job(job_id, status="done", progress=100, message=f"All compatible voices installed: {len(installed)} voices")

    except Exception as e:
        logger.exception("tts_offline_install_all_compatible failed: {}", sanitize_log_text(e))
        update_job(job_id, status="failed", progress=100,
                  message=f"Install failed: {str(e)[:200]}")
