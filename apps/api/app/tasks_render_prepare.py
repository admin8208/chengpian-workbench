from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlmodel import select

from app.jobs import update_job_in_session
from app.models import Asset, Project, Scene
from app.subtitles import normalize_subtitle_settings
from app.time_utils import now_utc


@dataclass
class RenderProjectSnapshot:
    id: int
    title: str
    workflow: str
    channel_key: str
    script: str
    voice_asset_id: int | None
    subtitle_asset_id: int | None


@dataclass
class RenderSceneSnapshot:
    id: int | None
    idx: int
    narration: str
    duration_sec: float
    image_asset_id: int | None
    meta_json: str


@dataclass
class RenderPreparation:
    project: RenderProjectSnapshot
    pid: int
    wf: str
    pack: Any
    cfg: dict
    rcfg: dict
    scenes: list[RenderSceneSnapshot]
    voice_name: str
    voice_rate: str
    voice_volume: float
    subtitle_style: str
    subtitle_overrides: dict
    target_w: int
    target_h: int
    aspect: str
    transition: str
    transition_sec: float
    motion_zoom: float


def prepare_render_context(
    *,
    session,
    project_id: int,
    target_job_id: int,
    rcfg_override: dict | None,
    get_pack,
    get_edge_voice_id,
    get_default_voice_rate,
):
    project = session.exec(select(Project).where(Project.id == project_id)).first()
    if not project:
        update_job_in_session(session, target_job_id, status="failed", progress=100, message="项目不存在")
        return None
    if project.id is None:
        update_job_in_session(session, target_job_id, status="failed", progress=100, message="项目 ID 缺失")
        return None
    pid = int(project.id)

    wf = (getattr(project, "workflow", "mix") or "mix").strip().lower()
    if wf != "mix":
        wf = "mix"

    pack = get_pack(session, project.channel_key)
    if not pack:
        update_job_in_session(session, target_job_id, status="failed", progress=100, message="频道内容包不存在")
        return None
    cfg = pack.config()
    edge_voice_default = get_edge_voice_id(session)
    default_voice_rate = get_default_voice_rate(session)

    voice_name = str(edge_voice_default or cfg.get("voice", "zh-CN-XiaoxiaoNeural"))
    voice_rate = str(default_voice_rate or "+0%")
    voice_volume = float(cfg.get("voice_volume", 1.0))
    subtitle_style = str(cfg.get("subtitle_style") or "boxed").strip().lower() or "boxed"
    if subtitle_style not in ("boxed", "clean"):
        subtitle_style = "boxed"

    rcfg = project.render_config() if hasattr(project, "render_config") else {}
    if isinstance(rcfg_override, dict) and rcfg_override:
        try:
            rcfg = {**(rcfg if isinstance(rcfg, dict) else {}), **rcfg_override}
        except Exception:
            pass
    if isinstance(rcfg, dict):
        if str(rcfg.get("voice", "")).strip():
            voice_name = str(rcfg.get("voice")).strip()
        if rcfg.get("voice_volume") is not None:
            try:
                voice_volume = float(rcfg.get("voice_volume"))
            except Exception:
                pass
        if str(rcfg.get("subtitle_style", "")).strip():
            subtitle_style = str(rcfg.get("subtitle_style")).strip()

    scenes = session.exec(select(Scene).where(Scene.project_id == pid).order_by(Scene.idx)).all()
    if not scenes:
        update_job_in_session(session, target_job_id, status="failed", progress=100, message="没有可渲染的镜头")
        return None

    project.status = "processing"
    project.updated_at = now_utc()
    session.add(project)

    target_w = 1920
    target_h = 1080
    aspect = "landscape"
    transition = "none"
    transition_sec = 0.0
    motion_zoom = 0.08
    subtitle_overrides: dict = {}
    if isinstance(rcfg, dict):
        try:
            if rcfg.get("width") is not None:
                target_w = int(rcfg.get("width"))
            if rcfg.get("height") is not None:
                target_h = int(rcfg.get("height"))
        except Exception:
            target_w, target_h = 1920, 1080
        if str(rcfg.get("aspect", "")).strip():
            aspect = str(rcfg.get("aspect")).strip().lower()
        if str(rcfg.get("transition", "")).strip():
            transition = str(rcfg.get("transition")).strip().lower()
        if rcfg.get("transition_sec") is not None:
            try:
                transition_sec = float(rcfg.get("transition_sec"))
            except Exception:
                transition_sec = 0.0
        if rcfg.get("motion_zoom") is not None:
            try:
                motion_zoom = float(rcfg.get("motion_zoom"))
            except Exception:
                motion_zoom = 0.08

        if rcfg.get("subtitle_boxed") is not None:
            subtitle_overrides["boxed"] = bool(rcfg.get("subtitle_boxed"))
        if str(rcfg.get("subtitle_font_name", "")).strip():
            subtitle_overrides["font_name"] = str(rcfg.get("subtitle_font_name")).strip()
        if rcfg.get("subtitle_font_size") is not None:
            subtitle_overrides["font_size"] = rcfg.get("subtitle_font_size")
        if str(rcfg.get("subtitle_position", "")).strip():
            subtitle_overrides["position"] = str(rcfg.get("subtitle_position")).strip().lower()
        if rcfg.get("subtitle_outline") is not None:
            subtitle_overrides["outline"] = rcfg.get("subtitle_outline")
        if rcfg.get("subtitle_margin_v") is not None:
            subtitle_overrides["margin_v"] = rcfg.get("subtitle_margin_v")
        subtitle_overrides["height"] = target_h

    subtitle_style, subtitle_overrides = normalize_subtitle_settings(subtitle_style, subtitle_overrides)

    if aspect == "landscape" and target_w == 1080 and target_h == 1920:
        target_w, target_h = 1920, 1080

    project_snapshot = RenderProjectSnapshot(
        id=pid,
        title=str(project.title or ""),
        workflow=str(project.workflow or "mix"),
        channel_key=str(project.channel_key or ""),
        script=str(project.script or ""),
        voice_asset_id=int(project.voice_asset_id) if project.voice_asset_id else None,
        subtitle_asset_id=int(project.subtitle_asset_id) if project.subtitle_asset_id else None,
    )
    scene_snapshots = [
        RenderSceneSnapshot(
            id=int(scene.id) if scene.id is not None else None,
            idx=int(scene.idx or 0),
            narration=str(scene.narration or ""),
            duration_sec=float(scene.duration_sec or 4.0),
            image_asset_id=int(scene.image_asset_id) if scene.image_asset_id else None,
            meta_json=str(scene.meta_json or ""),
        )
        for scene in scenes
    ]

    return RenderPreparation(
        project=project_snapshot,
        pid=pid,
        wf=wf,
        pack=pack,
        cfg=cfg,
        rcfg=rcfg if isinstance(rcfg, dict) else {},
        scenes=scene_snapshots,
        voice_name=voice_name,
        voice_rate=voice_rate,
        voice_volume=voice_volume,
        subtitle_style=subtitle_style,
        subtitle_overrides=subtitle_overrides,
        target_w=target_w,
        target_h=target_h,
        aspect=aspect,
        transition=transition,
        transition_sec=transition_sec,
        motion_zoom=motion_zoom,
    )
