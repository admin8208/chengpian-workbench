"""Composable TTS router."""

import os

from fastapi import APIRouter, HTTPException

from app.api_common import job_out
from app.db import session_scope
from app.file_access import signed_file_url
from app.ffmpeg_utils import ffmpeg_path, run_ffmpeg
from app.jobs import create_job, ensure_enqueued
from app.modules.tts.catalog import DEFAULT_VOICE_ID
from app.modules.tts.offline import (
    cleanup_incompatible_offline_voices,
    list_offline_voices,
    offline_piper_audio_only,
)
from app.modules.tts.runtime import edge_tts_audio_only
from app.modules.tts.service import get_default_voice_rate, get_edge_voice_id, get_offline_voice_id, get_tts_backend, set_default_voice_rate, set_edge_voice_id, set_offline_voice_id, set_tts_backend, tts_status_dict
from app.schemas import JobCreateOut, OfflineVoiceCleanupOut, TtsBackendIn, TtsPreviewIn, TtsPreviewOut, TtsStatusOut
from app.settings import settings
from app.tasks_tts_install import tts_offline_install, tts_offline_install_all_compatible
from app.time_utils import now_utc

router = APIRouter(tags=["tts"])


@router.post("/api/tts/preview", response_model=TtsPreviewOut)
def preview_tts(body: TtsPreviewIn):
    text = (body.text or "").strip()
    voice = (body.voice or "").strip()
    rate = (body.rate or "+0%").strip()
    volume = float(body.volume or 1.0)
    preview_backend = str(body.backend or "").strip().lower()
    preview_offline_voice_id = str(body.offline_voice_id or "").strip()

    if not text:
        return TtsPreviewOut(ok=False, error="text 不能为空")
    if not voice:
        return TtsPreviewOut(ok=False, error="voice 不能为空")

    ts = now_utc().strftime("%Y%m%d_%H%M%S")
    out_dir = settings.exports_dir / "tts_previews"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / f"preview_{ts}.mp3"
    out_path = raw_path

    try:
        backend = "offline_piper"
        offline_voice_id = DEFAULT_VOICE_ID
        edge_voice_id = "zh-CN-XiaoxiaoNeural"
        with session_scope() as session:
            backend = get_tts_backend(session)
            offline_voice_id = get_offline_voice_id(session)
            edge_voice_id = get_edge_voice_id(session)
            default_rate = get_default_voice_rate(session)
        if preview_backend in ("offline_piper", "edge", "auto"):
            backend = preview_backend
        if not str(body.rate or "").strip():
            rate = default_rate
        if preview_offline_voice_id:
            offline_voice_id = preview_offline_voice_id
        if voice.strip():
            edge_voice_id = voice.strip()

        if backend == "offline_piper":
            wav_path = raw_path.with_suffix(".wav")
            offline_piper_audio_only(text=text[:400], voice_id=str(offline_voice_id or DEFAULT_VOICE_ID), wav_path=wav_path)
            run_ffmpeg(["-y", "-i", ffmpeg_path(wav_path), "-c:a", "libmp3lame", "-b:a", "128k", ffmpeg_path(raw_path)], timeout_s=90)
            try:
                wav_path.unlink(missing_ok=True)
            except Exception:
                pass
        else:
            edge_tts_audio_only(text=text[:400], voice=edge_voice_id, rate=rate, audio_path=raw_path, timeout_s=20)

        if abs(volume - 1.0) > 1e-3:
            adj = out_dir / f"preview_{ts}_v.mp3"
            try:
                run_ffmpeg(["-y", "-i", ffmpeg_path(raw_path), "-filter:a", f"volume={volume}", ffmpeg_path(adj)], timeout_s=45)
                if adj.exists() and adj.stat().st_size > 0:
                    out_path = adj
            except Exception:
                out_path = raw_path

        try:
            keep_preview = max(0, min(30, int(os.environ.get("CHENGPIAN_KEEP_TTS_PREVIEWS", "3"))))
        except Exception:
            keep_preview = 3
        try:
            rows = sorted([p for p in out_dir.glob("preview_*.mp3") if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)
            for old in rows[keep_preview:]:
                try:
                    old.unlink(missing_ok=True)
                except Exception:
                    pass
        except Exception:
            pass

        return TtsPreviewOut(ok=True, url=signed_file_url('exports', f"tts_previews/{out_path.name}"))
    except Exception as e:
        return TtsPreviewOut(ok=False, error=str(e))


@router.get("/api/tts/status", response_model=TtsStatusOut)
def get_tts_status(probe: bool = False):
    with session_scope() as session:
        return TtsStatusOut(**tts_status_dict(session=session, probe_edge=bool(probe)))


@router.post("/api/tts/backend", response_model=TtsStatusOut)
def set_tts_backend_api(body: TtsBackendIn):
    with session_scope() as session:
        set_tts_backend(session, body.backend)
        if body.offline_voice_id is not None:
            set_offline_voice_id(session, body.offline_voice_id)
        if body.edge_voice_id is not None:
            set_edge_voice_id(session, body.edge_voice_id)
        if body.default_voice_rate is not None:
            set_default_voice_rate(session, body.default_voice_rate)
        return TtsStatusOut(**tts_status_dict(session=session, probe_edge=False))


@router.post("/api/tts/offline/install", response_model=JobCreateOut)
def install_offline_tts(body: TtsBackendIn | None = None):
    voice_id = str(body.offline_voice_id) if body and body.offline_voice_id else ""
    job = create_job("tts_offline_install", project_id=0, message="排队中", payload={"voice_id": voice_id})
    if job.id is None:
        raise HTTPException(status_code=500, detail="创建安装任务失败")
    job_id = int(job.id)
    result = tts_offline_install.schedule(args=(job_id,), kwargs={"voice_id": voice_id}, delay=0)
    try:
        ensure_enqueued(result, error_message="离线音色安装任务入队失败，请检查后台任务服务")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return JobCreateOut(job=job_out(job_id))


@router.post("/api/tts/offline/install-all-compatible", response_model=JobCreateOut)
def install_all_compatible():
    job = create_job("tts_offline_install_all_compatible", project_id=0, message="排队中", payload={})
    if job.id is None:
        raise HTTPException(status_code=500, detail="创建安装任务失败")
    job_id = int(job.id)
    result = tts_offline_install_all_compatible.schedule(args=(job_id,), delay=0)
    try:
        ensure_enqueued(result, error_message="兼容离线音色安装任务入队失败，请检查后台任务服务")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return JobCreateOut(job=job_out(job_id))


@router.post("/api/tts/offline/cleanup-incompatible", response_model=OfflineVoiceCleanupOut)
def cleanup_incompatible_voices():
    res = cleanup_incompatible_offline_voices()
    try:
        installed = [str(v.get("voice_id")) for v in (list_offline_voices() or []) if v.get("voice_id")]
        fallback = DEFAULT_VOICE_ID if DEFAULT_VOICE_ID in installed else (installed[0] if installed else DEFAULT_VOICE_ID)
        with session_scope() as session:
            cur = str(get_offline_voice_id(session) or "").strip()
            if cur not in installed:
                set_offline_voice_id(session, fallback)
    except Exception:
        pass
    return OfflineVoiceCleanupOut(ok=True, deleted_voice_ids=res.get("deleted_voice_ids") or [], freed_bytes=int(res.get("freed_bytes") or 0))
