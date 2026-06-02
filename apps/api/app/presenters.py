import json

from sqlmodel import select

from app.file_access import signed_file_url
from app.models import Asset, Project, Scene
from app.schemas import AssetOut, ProjectOut, SceneOut


def _asset_url(a: Asset) -> str:
    rel = str(a.rel_path or "").lstrip("/")
    if rel.startswith("project_"):
        return signed_file_url('projects', rel)
    tag = str(a.tag or "").strip().lower()
    if a.kind == "video" and tag in ("export", "export_history"):
        return signed_file_url('exports', rel)
    return signed_file_url('assets', rel)


def asset_to_out(a: Asset) -> AssetOut:
    meta: dict = {}
    try:
        meta = json.loads(getattr(a, "meta_json", "") or "{}")
        if not isinstance(meta, dict):
            meta = {}
    except Exception:
        meta = {}
    asset_id = getattr(a, "id", None)
    if asset_id is None:
        raise ValueError("asset id is required")
    return AssetOut(
        id=int(asset_id),
        kind=a.kind,
        tag=a.tag or "",
        project_id=a.project_id,
        scene_id=a.scene_id,
        url=_asset_url(a),
        mime=a.mime or "",
        meta=meta,
        created_at=a.created_at,
    )


def scene_to_out(session, s: Scene) -> SceneOut:
    image_url = None
    if s.image_asset_id:
        asset = session.exec(select(Asset).where(Asset.id == s.image_asset_id)).first()
        if asset:
            image_url = _asset_url(asset)
    meta = {}
    try:
        meta = json.loads(getattr(s, "meta_json", "{}") or "{}")
        if not isinstance(meta, dict):
            meta = {}
    except Exception:
        meta = {}
    scene_id = getattr(s, "id", None)
    if scene_id is None:
        raise ValueError("scene id is required")
    return SceneOut(
        id=int(scene_id),
        project_id=s.project_id,
        idx=s.idx,
        narration=s.narration,
        media_query=getattr(s, "media_query", "") or "",
        image_prompt=s.image_prompt,
        image_negative=s.image_negative or "",
        duration_sec=s.duration_sec,
        image_asset_id=s.image_asset_id,
        image_url=image_url,
        meta=meta,
        status=s.status,
    )


def _project_asset_url(session, asset_id: int | None) -> str | None:
    if not asset_id:
        return None
    asset = session.exec(select(Asset).where(Asset.id == asset_id)).first()
    if not asset:
        return None
    return _asset_url(asset)


def project_to_out(session, p: Project) -> ProjectOut:
    project_id = getattr(p, "id", None)
    if project_id is None:
        raise ValueError("project id is required")
    return ProjectOut(
        id=int(project_id),
        title=p.title,
        workflow=getattr(p, "workflow", "mix") or "mix",
        channel_key=p.channel_key,
        status=p.status,
        script=p.script,
        script_source=(getattr(p, "script_source", "") or ""),
        source_text=p.source_text or "",
        character_profile=p.character_profile or "",
        publish_title=p.publish_title or "",
        publish_hashtags=p.publish_hashtags or "",
        render_config=p.render_config(),
        voice_asset_id=p.voice_asset_id,
        subtitle_asset_id=p.subtitle_asset_id,
        confirmed_baseline_revision_id=getattr(p, "confirmed_baseline_revision_id", None),
        current_pipeline_run_id=getattr(p, "current_pipeline_run_id", None),
        role_image_url=_project_asset_url(session, p.role_image_asset_id),
        voice_url=_project_asset_url(session, p.voice_asset_id),
        subtitle_url=_project_asset_url(session, p.subtitle_asset_id),
        created_at=p.created_at,
        updated_at=p.updated_at,
    )
