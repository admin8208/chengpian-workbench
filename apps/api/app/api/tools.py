from __future__ import annotations

import json
import mimetypes
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlmodel import select

from app.access_control import owner_fields_for_current_principal
from app.ffmpeg_utils import ffmpeg_path, run_ffmpeg
from app.file_access import signed_file_url
from app.models import Asset, ChannelPack, Project
from app.presenters import project_to_out
from app.schemas.tools import VideoToAudioOut, VideoToAudioProjectIn, VideoToAudioProjectOut, VideoUrlToAudioIn
from app.db import session_scope
from app.settings import settings
from app.time_utils import now_utc

router = APIRouter(tags=["tools"])


def _allowed_video_suffix(suffix: str) -> bool:
    return suffix.lower() in {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


@router.post("/api/tools/video-to-audio", response_model=VideoToAudioOut)
async def video_to_audio(file: UploadFile = File(...), output_format: str = Form("mp3")):
    suffix = Path(file.filename or "upload").suffix.lower()
    if not _allowed_video_suffix(suffix):
        raise HTTPException(status_code=400, detail="仅支持 mp4/mov/mkv/webm/avi/m4v 视频文件")
    fmt = str(output_format or "mp3").strip().lower()
    if fmt != "mp3":
        raise HTTPException(status_code=400, detail="当前仅支持导出 mp3")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(raw) > 1024 * 1024 * 700:
        raise HTTPException(status_code=400, detail="视频文件过大，请控制在 700MB 以内")

    ts = now_utc().strftime("%Y%m%d_%H%M%S_%f")
    work_dir = settings.data_dir / "tools" / "video_to_audio" / ts
    work_dir.mkdir(parents=True, exist_ok=True)
    input_path = work_dir / f"input{suffix}"
    input_path.write_bytes(raw)
    output_name = f"audio_{ts}.mp3"
    output_path = work_dir / output_name

    try:
        run_ffmpeg([
            "-y",
            "-i",
            ffmpeg_path(input_path),
            "-vn",
            "-acodec",
            "libmp3lame",
            "-b:a",
            "192k",
            ffmpeg_path(output_path),
        ], timeout_s=600)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"视频转音频失败：{exc}") from exc

    if not output_path.exists() or not output_path.is_file() or output_path.stat().st_size <= 0:
        raise HTTPException(status_code=500, detail="视频转音频失败：未生成有效音频文件")

    rel = str(output_path.relative_to(settings.data_dir / "tools")).replace("\\", "/")
    mime = mimetypes.guess_type(output_name)[0] or "audio/mpeg"
    return VideoToAudioOut(
        ok=True,
        filename=output_name,
        mime=mime,
        size=int(output_path.stat().st_size or 0),
        url=signed_file_url("tools", rel),
        rel_path=rel,
    )


@router.post("/api/tools/video-url-to-audio", response_model=VideoToAudioOut)
async def video_url_to_audio(body: VideoUrlToAudioIn):
    """从视频链接下载并转音频"""
    url = str(body.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="请输入视频链接")

    ts = now_utc().strftime("%Y%m%d_%H%M%S_%f")
    work_dir = settings.data_dir / "tools" / "video_to_audio" / ts
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        import yt_dlp

        ydl_opts = {
            'outtmpl': str(work_dir / 'video.%(ext)s'),
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_path = None
            for f in work_dir.iterdir():
                if f.is_file() and f.suffix in ('.mp4', '.mkv', '.webm', '.avi', '.mov', '.m4v', '.flv'):
                    video_path = f
                    break

            if not video_path:
                downloaded = ydl.prepare_filename(info)
                if Path(downloaded).exists():
                    video_path = Path(downloaded)

            if not video_path or not video_path.exists():
                raise HTTPException(status_code=500, detail="视频下载失败")

    except ImportError:
        raise HTTPException(status_code=500, detail="yt-dlp 未安装，请联系管理员")
    except Exception as e:
        error_msg = str(e)
        if 'Unsupported URL' in error_msg:
            raise HTTPException(status_code=400, detail="不支持的视频链接格式")
        if 'Video unavailable' in error_msg:
            raise HTTPException(status_code=400, detail="视频不可用或已被删除")
        raise HTTPException(status_code=500, detail=f"视频下载失败：{error_msg[:200]}")

    output_name = f"audio_{ts}.mp3"
    output_path = work_dir / output_name

    try:
        run_ffmpeg([
            "-y",
            "-i",
            ffmpeg_path(video_path),
            "-vn",
            "-acodec",
            "libmp3lame",
            "-b:a",
            "192k",
            ffmpeg_path(output_path),
        ], timeout_s=600)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"视频转音频失败：{exc}") from exc

    if not output_path.exists() or not output_path.is_file() or output_path.stat().st_size <= 0:
        raise HTTPException(status_code=500, detail="视频转音频失败：未生成有效音频文件")

    rel = str(output_path.relative_to(settings.data_dir / "tools")).replace("\\", "/")
    mime = mimetypes.guess_type(output_name)[0] or "audio/mpeg"
    return VideoToAudioOut(
        ok=True,
        filename=output_name,
        mime=mime,
        size=int(output_path.stat().st_size or 0),
        url=signed_file_url("tools", rel),
        rel_path=rel,
    )


@router.post("/api/tools/video-to-audio/project", response_model=VideoToAudioProjectOut)
def create_audio_project_from_tool(body: VideoToAudioProjectIn):
    rel = str(body.rel_path or "").strip().lstrip("/")
    if not rel:
        raise HTTPException(status_code=400, detail="缺少音频文件路径")
    src = (settings.data_dir / "tools" / rel).resolve()
    base = (settings.data_dir / "tools").resolve()
    if (src != base and base not in src.parents) or not src.exists() or not src.is_file():
        raise HTTPException(status_code=400, detail="音频文件不存在或路径无效")

    material_mode = str(body.material_mode or "network").strip().lower()
    if material_mode not in ("network", "ai"):
        raise HTTPException(status_code=400, detail="material_mode 只能是 network/ai")

    with session_scope() as session:
        pack = session.exec(select(ChannelPack).where(ChannelPack.key == body.channel_key)).first()
        if not pack:
            raise HTTPException(status_code=400, detail="未知的频道 key")
        title = str(body.title or "").strip() or f"音频项目 {now_utc().strftime('%H:%M:%S')}"
        project = Project(title=title, **owner_fields_for_current_principal(), workflow="mix", channel_key=body.channel_key, status="draft", source_text="")
        project.render_config_json = json.dumps({
            "aspect": "landscape",
            "width": 1920,
            "height": 1080,
            "material_mode": material_mode,
            "input_mode": "audio",
            "subtitle_style": "boxed",
            "subtitle_font_size": 22,
            "subtitle_position": "bottom",
            "subtitle_margin_v": 32,
            "subtitle_outline": 1.4,
            "subtitle_boxed": True,
        }, ensure_ascii=True)
        session.add(project)
        session.flush()
        session.refresh(project)
        if project.id is None:
            raise HTTPException(status_code=500, detail="创建项目失败")

        from app.project_paths import project_imported_dir, rel_to_projects_root

        target_dir = project_imported_dir(int(project.id)) / "audio"
        target_dir.mkdir(parents=True, exist_ok=True)
        ts = now_utc().strftime("%Y%m%d_%H%M%S_%f")
        target = target_dir / f"voice_upload_{ts}.mp3"
        target.write_bytes(src.read_bytes())
        asset = Asset(
            kind="audio",
            rel_path=rel_to_projects_root(target),
            mime="audio/mpeg",
            project_id=int(project.id),
            tag="project_source",
            meta_json=json.dumps({
                "provider": "video_to_audio_tool",
                "title": title,
                "source_tool_rel_path": rel,
            }, ensure_ascii=True),
        )
        session.add(asset)
        session.flush()
        session.refresh(asset)
        if asset.id is None:
            raise HTTPException(status_code=500, detail="音频资产绑定失败")
        project.voice_asset_id = int(asset.id)
        project.updated_at = now_utc()
        session.add(project)
        return VideoToAudioProjectOut(ok=True, project_id=int(project.id))
