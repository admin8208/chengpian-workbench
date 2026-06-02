"""Task helper functions - extracted from tasks.py"""
from __future__ import annotations

from pathlib import Path
from loguru import logger

from app.settings import settings


def naturalize_voice_rate(rate: str) -> str:
    """Normalize voice rate string."""
    try:
        r = str(rate or "").strip().lower()
        if not r or r in ("normal", "default", "1", "1.0", "1x"):
            return "1.0"
        r = r.replace("x", "").replace("+", "")
        return str(max(0.5, min(2.0, float(r))))
    except Exception:
        return "1.0"


def project_voice_rate(rcfg: dict | None) -> str:
    """Get voice rate from render config."""
    return naturalize_voice_rate((rcfg or {}).get("voice_rate", "normal"))


def friendly_tts_failure_message(detail: str) -> str:
    """Convert TTS error to user-friendly message."""
    d = str(detail or "").strip()
    low = d.lower()
    if not d:
        return "配音生成失败，请重试。"
    if "edge tts" in low and "failed" in low:
        return f"在线配音生成失败：{d[:200]}"
    if "offline" in low or "piper" in low:
        return "离线配音不可用，请检查 设置 -> 配音。"
    if "no such filter" in low and "rubberband" in low:
        return "音频处理环境缺少 rubberband 滤镜，请更新后重试。"
    if "ffmpeg" in low or "rubberband" in low:
        return f"音频处理环境异常：{d[:200]}"
    return f"配音生成失败：{d[:200]}"


def humanize_render_error(detail: str) -> str:
    """Convert render error to user-friendly message."""
    raw = str(detail or "").strip()
    low = raw.lower()
    if not raw:
        return "渲染失败，请重试。"
    if raw in ("cancelled", "__job_cancelled__"):
        return "任务已取消。"
    if "timeout" in low:
        return "渲染超时，请重试。"
    if "no such filter" in low and "rubberband" in low:
        return "音频处理环境缺少 rubberband 滤镜，请更新后重试。"
    if "ffmpeg" in low or "rubberband" in low:
        return f"音视频处理异常：{raw[:200]}"
    return f"渲染失败：{raw[:200]}"


def classify_media_provider_error(detail: str) -> tuple[str, str]:
    """Classify media provider error."""
    d = str(detail or "").strip().lower()
    if "timeout" in d or "timed out" in d:
        return ("media_timeout", "Media search timed out")
    if "api key" in d or "unauthorized" in d or "401" in d:
        return ("media_auth_error", "Media API key invalid")
    if "rate limit" in d or "429" in d:
        return ("media_rate_limit", "Media API rate limited")
    if "not found" in d or "404" in d:
        return ("media_not_found", "No media found")
    return ("media_error", f"Media search failed: {detail[:150]}")


def fail_job(job_id: int, *, message: str, error_code: str = "unknown",
             blocking_component: str = "project", recommended_action: str = "open_project",
             recoverable: bool = True) -> None:
    """Mark a job as failed with detailed info."""
    from app.jobs import patch_job_payload, update_job

    patch_job_payload(
        job_id,
        {
            "error_code": str(error_code or "unknown"),
            "blocking_component": str(blocking_component or "project"),
            "recommended_action": str(recommended_action or "open_project"),
            "recoverable": bool(recoverable),
        },
    )
    update_job(
        job_id,
        status="failed",
        progress=100,
        message=message,
    )
