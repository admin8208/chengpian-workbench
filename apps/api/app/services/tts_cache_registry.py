import json

from sqlmodel import select

from app.db import session_scope
from app.models import AppConfig, Asset
from app.project_paths import asset_disk_path
from app.settings import settings


def _project_tts_cache_config_key(project_id: int) -> str:
    return f"project_tts_cache_refs:{int(project_id)}"


def register_project_tts_cache_refs(project_id: int, rel_paths: list[str]) -> None:
    refs = sorted({str(x or "").strip().lstrip("/") for x in (rel_paths or []) if str(x or "").strip()})
    if not refs:
        return
    with session_scope() as session:
        key = _project_tts_cache_config_key(project_id)
        row = session.exec(select(AppConfig).where(AppConfig.key == key)).first()
        payload = json.dumps(refs, ensure_ascii=True)
        if row:
            row.value = payload
            session.add(row)
        else:
            session.add(AppConfig(key=key, value=payload))


def cleanup_project_tts_cache_refs(project_id: int) -> list[str]:
    leftovers: list[str] = []
    with session_scope() as session:
        key = _project_tts_cache_config_key(project_id)
        row = session.exec(select(AppConfig).where(AppConfig.key == key)).first()
        if not row:
            return leftovers
        try:
            refs = json.loads(row.value or "[]")
        except Exception:
            refs = []
        if not isinstance(refs, list):
            refs = []
        for rel in refs:
            try:
                path = asset_disk_path(str(rel or ""), is_export=False)
                if path.exists():
                    path.unlink(missing_ok=True)
                if path.exists():
                    leftovers.append(str(path))
            except Exception:
                leftovers.append(str(rel))
        session.delete(row)
    return leftovers


def cleanup_unreferenced_tts_cache() -> list[str]:
    removed: list[str] = []
    active_refs: set[str] = set()
    with session_scope() as session:
        rows = session.exec(select(Asset).where(Asset.tag.in_(["voice_generated", "subtitle_generated"]))).all()
        for asset in rows:
            rel = str(getattr(asset, "rel_path", "") or "").strip().lstrip("/")
            if rel:
                active_refs.add(rel)
    cache_dir = settings.assets_dir / "tts_cache"
    if not cache_dir.exists():
        return removed
    for path in cache_dir.glob("*"):
        if not path.is_file():
            continue
        rel = f"tts_cache/{path.name}"
        if rel in active_refs:
            continue
        try:
            path.unlink(missing_ok=True)
            if not path.exists():
                removed.append(rel)
        except Exception:
            continue
    return removed
