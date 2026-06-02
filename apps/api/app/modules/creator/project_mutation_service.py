import json
import re

from fastapi import HTTPException
from sqlmodel import select

from app.access_control import owner_fields_for_current_principal, require_project_access
from app.api_common import default_render_dimensions, ensure_project_storage_clean
from app.db import session_scope
from app.material_policies import normalize_material_mode, project_material_mode
from app.models import Asset, ChannelPack, Project
from app.modules.baseline.invalidation import invalidate_confirmed_baseline_chain
from app.modules.pipeline.state import project_has_confirmed_baseline
from app.projection_refresh import schedule_project_refresh
from app.schemas import ProjectCreateIn, ProjectOut
from app.time_utils import now_utc


def validate_render_config(cfg: dict, *, normalize_subtitle_settings) -> dict:
    if not isinstance(cfg, dict):
        raise HTTPException(status_code=400, detail="render_config 必须是 JSON 对象")
    out = dict(cfg)

    def as_str(key: str, max_len: int = 4000) -> None:
        if key not in out:
            return
        value = str(out[key])
        if len(value) > max_len:
            raise HTTPException(status_code=400, detail=f"{key} 过长")
        out[key] = value

    def sync_dimensions_from_aspect() -> None:
        aspect = str(out.get("aspect") or "landscape").strip().lower() or "landscape"
        width, height = default_render_dimensions(aspect)
        out["aspect"] = aspect
        out["width"] = width
        out["height"] = height

    def as_int(key: str, lo: int, hi: int) -> None:
        if key not in out:
            return
        try:
            value = int(out[key])
        except Exception:
            raise HTTPException(status_code=400, detail=f"{key} 必须是整数")
        if value < lo or value > hi:
            raise HTTPException(status_code=400, detail=f"{key} 超出范围（{lo}-{hi}）")
        out[key] = value

    def as_float(key: str, lo: float, hi: float) -> None:
        if key not in out:
            return
        try:
            value = float(out[key])
        except Exception:
            raise HTTPException(status_code=400, detail=f"{key} 必须是数字")
        if value < lo or value > hi:
            raise HTTPException(status_code=400, detail=f"{key} 超出范围（{lo}-{hi}）")
        out[key] = value

    as_int("width", 480, 3840)
    as_int("height", 480, 3840)
    as_str("aspect", 20)
    if "aspect" in out:
        aspect = str(out["aspect"]).strip().lower()
        if aspect not in ("landscape", "portrait"):
            raise HTTPException(status_code=400, detail="aspect 只能是 landscape/portrait")
        out["aspect"] = aspect
        sync_dimensions_from_aspect()
    as_str("transition", 20)
    if "transition" in out:
        transition = str(out["transition"]).strip().lower()
        if transition not in ("none", "crossfade"):
            raise HTTPException(status_code=400, detail="transition 只能是 none 或 crossfade")
        out["transition"] = transition
    as_float("transition_sec", 0.0, 1.2)
    as_float("motion_zoom", 0.0, 0.25)
    as_float("target_min_sec", 10.0, 300.0)
    as_float("target_max_sec", 10.0, 300.0)
    as_float("target_sec", 10.0, 300.0)
    if "target_min_sec" in out and "target_max_sec" in out and float(out["target_min_sec"]) > float(out["target_max_sec"]):
        raise HTTPException(status_code=400, detail="target_min_sec 不能大于 target_max_sec")
    if "target_sec" in out:
        if "target_min_sec" in out and float(out["target_sec"]) < float(out["target_min_sec"]):
            raise HTTPException(status_code=400, detail="target_sec 不能小于 target_min_sec")
        if "target_max_sec" in out and float(out["target_sec"]) > float(out["target_max_sec"]):
            raise HTTPException(status_code=400, detail="target_sec 不能大于 target_max_sec")
    as_str("voice", 80)
    as_str("voice_rate", 10)
    if "voice_rate" in out:
        voice_rate = str(out["voice_rate"]).strip()
        if not re.match(r"^[+-]?\d+%$", voice_rate):
            raise HTTPException(status_code=400, detail="voice_rate 格式应类似 +10%")
        out["voice_rate"] = voice_rate
    as_float("voice_volume", 0.0, 2.0)
    as_str("material_mode", 20)
    if "material_mode" in out:
        out["material_mode"] = normalize_material_mode(out.get("material_mode"))
    as_str("input_mode", 20)
    if "input_mode" in out:
        input_mode = str(out["input_mode"]).strip().lower() or "text"
        if input_mode not in ("text", "audio"):
            raise HTTPException(status_code=400, detail="input_mode 只能是 text/audio")
        out["input_mode"] = input_mode
    as_str("media_pick_mode", 30)
    if "media_pick_mode" in out:
        media_pick_mode = str(out["media_pick_mode"]).strip().lower() or "smart"
        if media_pick_mode not in ("smart", "random_video"):
            raise HTTPException(status_code=400, detail="media_pick_mode 只能是 smart/random_video")
        material_mode = normalize_material_mode(out.get("material_mode"))
        if media_pick_mode == "random_video" and material_mode != "network":
            raise HTTPException(status_code=400, detail="随机视频只能用于素材模式")
        out["media_pick_mode"] = media_pick_mode
    as_str("subtitle_style", 20)
    if "subtitle_style" in out:
        subtitle_style = str(out["subtitle_style"]).strip()
        if subtitle_style not in ("boxed", "clean"):
            raise HTTPException(status_code=400, detail="subtitle_style 只能是 boxed/clean")
        out["subtitle_style"] = subtitle_style
    as_str("subtitle_font_name", 120)
    as_int("subtitle_font_size", 16, 120)
    as_str("subtitle_position", 20)
    if "subtitle_position" in out:
        subtitle_position = str(out["subtitle_position"]).strip().lower()
        if subtitle_position not in ("top", "center", "bottom"):
            raise HTTPException(status_code=400, detail="subtitle_position 只能是 top/center/bottom")
        out["subtitle_position"] = subtitle_position
    as_float("subtitle_outline", 0.0, 10.0)
    as_int("subtitle_margin_v", 0, 400)
    if "subtitle_boxed" in out:
        out["subtitle_boxed"] = bool(out["subtitle_boxed"])
    try:
        subtitle_style = str(out.get("subtitle_style") or "boxed").strip().lower() or "boxed"
        subtitle_cfg = {
            "font_name": out.get("subtitle_font_name"),
            "font_size": out.get("subtitle_font_size"),
            "position": out.get("subtitle_position"),
            "outline": out.get("subtitle_outline"),
            "margin_v": out.get("subtitle_margin_v"),
            "boxed": out.get("subtitle_boxed"),
            "height": out.get("height"),
        }
        subtitle_style, safe_sub = normalize_subtitle_settings(subtitle_style, subtitle_cfg)
        out["subtitle_style"] = subtitle_style
        if "font_size" in safe_sub:
            out["subtitle_font_size"] = int(safe_sub["font_size"])
        if "position" in safe_sub:
            out["subtitle_position"] = str(safe_sub["position"])
        if "margin_v" in safe_sub:
            out["subtitle_margin_v"] = int(safe_sub["margin_v"])
        if "outline" in safe_sub:
            out["subtitle_outline"] = float(safe_sub["outline"])
        if "boxed" in safe_sub:
            out["subtitle_boxed"] = bool(safe_sub["boxed"])
    except Exception:
        pass
    return out


def create_project_api(project_to_out, body: ProjectCreateIn, *, normalize_subtitle_settings) -> ProjectOut:
    with session_scope() as session:
        pack = session.exec(select(ChannelPack).where(ChannelPack.key == body.channel_key)).first()
        if not pack:
            raise HTTPException(status_code=400, detail="未知的频道 key")
        project = Project(
            title=body.title.strip(),
            **owner_fields_for_current_principal(),
            workflow="mix",
            channel_key=body.channel_key,
            status="draft",
            source_text=(body.source_text or "").strip(),
        )
        requested_aspect = str(((body.render_config or {}) or {}).get("aspect") or "landscape").strip().lower() or "landscape"
        width, height = default_render_dimensions(requested_aspect)
        base_cfg = {"aspect": requested_aspect, "width": width, "height": height}
        try:
            cfg = validate_render_config({**base_cfg, **(body.render_config or {})}, normalize_subtitle_settings=normalize_subtitle_settings)
            project.render_config_json = json.dumps(cfg, ensure_ascii=True)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="render_config JSON 不合法")
        session.add(project)
        session.flush()
        session.refresh(project)
        if project.id is None:
            raise HTTPException(status_code=500, detail="创建项目失败")
        leftovers = ensure_project_storage_clean(int(project.id))
        if leftovers:
            sample = "；".join(leftovers[:3])
            raise HTTPException(status_code=500, detail=f"创建项目失败：检测到旧项目残留目录未清理干净：{sample}")
        schedule_project_refresh(session, int(project.id))
        return project_to_out(session, project)


def patch_project_api(project_id: int, body, *, project_to_out, normalize_subtitle_settings) -> ProjectOut:
    with session_scope() as session:
        project = require_project_access(session, project_id)
        if body.title is not None:
            project.title = body.title.strip()
        if getattr(body, "script", None) is not None:
            was_confirmed = project_has_confirmed_baseline(project)
            project.script = (body.script or "").strip()
            if project.script:
                project.script_source = "manual"
            else:
                project.script_source = ""
            if was_confirmed:
                invalidate_confirmed_baseline_chain(session, project)
        if getattr(body, "source_text", None) is not None:
            project.source_text = (body.source_text or "").strip()
            if project_has_confirmed_baseline(project):
                invalidate_confirmed_baseline_chain(session, project)
        if body.character_profile is not None:
            project.character_profile = body.character_profile.strip()
        if body.publish_title is not None:
            project.publish_title = body.publish_title.strip()
        if body.publish_hashtags is not None:
            project.publish_hashtags = body.publish_hashtags.strip()
        if getattr(body, "voice_asset_id", None) is not None:
            if body.voice_asset_id:
                asset = session.exec(select(Asset).where(Asset.id == int(body.voice_asset_id))).first()
                if not asset or asset.id is None:
                    raise HTTPException(status_code=404, detail="音频素材不存在")
                if int(asset.project_id or 0) != int(project.id):
                    raise HTTPException(status_code=400, detail="音频素材不属于当前项目")
                if str(asset.kind or "") != "audio":
                    raise HTTPException(status_code=400, detail="voice_asset_id 必须绑定音频素材")
                project.voice_asset_id = int(asset.id)
            else:
                project.voice_asset_id = None
        if getattr(body, "subtitle_asset_id", None) is not None:
            if body.subtitle_asset_id:
                asset = session.exec(select(Asset).where(Asset.id == int(body.subtitle_asset_id))).first()
                if not asset or asset.id is None:
                    raise HTTPException(status_code=404, detail="字幕素材不存在")
                if int(asset.project_id or 0) != int(project.id):
                    raise HTTPException(status_code=400, detail="字幕素材不属于当前项目")
                suffix = str(getattr(asset, "rel_path", "") or "").lower()
                if str(asset.kind or "") not in ("other", "audio") and not suffix.endswith((".srt", ".vtt", ".ass")):
                    raise HTTPException(status_code=400, detail="subtitle_asset_id 必须绑定字幕素材")
                project.subtitle_asset_id = int(asset.id)
            else:
                project.subtitle_asset_id = None
        base_cfg = project.render_config() if hasattr(project, "render_config") else {}
        if not isinstance(base_cfg, dict):
            base_cfg = {}
        if body.render_config is not None:
            try:
                incoming_cfg = dict(body.render_config or {})
                old_mode = project_material_mode(project, render_cfg=base_cfg)
                requested_mode = project_material_mode(None, render_cfg={**base_cfg, **incoming_cfg})
                if requested_mode != old_mode:
                    raise HTTPException(status_code=409, detail="material_mode 在项目创建后即锁定，项目执行过程中不支持切换智能生图模式和素材模式")
                cfg = validate_render_config({**base_cfg, **incoming_cfg}, normalize_subtitle_settings=normalize_subtitle_settings)
                project.render_config_json = json.dumps(cfg, ensure_ascii=True)
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=400, detail="render_config JSON 不合法")
        project.updated_at = now_utc()
        session.add(project)
        session.flush()
        session.refresh(project)
        schedule_project_refresh(session, int(project.id))
        return project_to_out(session, project)
