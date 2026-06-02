from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlmodel import select

from app.db import session_scope
from app.models import Asset, Project, Scene
from app.project_paths import asset_disk_path


def _asset_meta(asset: Asset) -> dict:
    try:
        obj = json.loads(getattr(asset, "meta_json", "{}") or "{}")
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _asset_exists(asset: Asset) -> bool:
    rel = str(getattr(asset, "rel_path", "") or "").strip()
    if not rel:
        return False
    is_export = bool(str(asset.kind or "") == "video" and str(asset.tag or "") in ("export", "export_candidate", "export_history"))
    p = asset_disk_path(rel, is_export=is_export)
    return p.exists() and p.is_file()


def _project_titles() -> dict[int, str]:
    with session_scope() as session:
        rows = session.exec(select(Project)).all()
        return {int(p.id): str(p.title or "") for p in rows if getattr(p, "id", None) is not None}


def main() -> None:
    titles = _project_titles()
    with session_scope() as session:
        library_assets = session.exec(select(Asset).where(Asset.tag == "library")).all()
        project_assets = session.exec(select(Asset).where(Asset.project_id != None)).all()  # noqa: E711
        bound_library_assets = session.exec(
            select(Asset)
            .join(Scene, Scene.image_asset_id == Asset.id)
            .where(Asset.tag == "library")
        ).all()

    invalid_library: list[dict] = []
    suspicious_library: list[dict] = []
    project_assets_in_library_path: list[dict] = []
    project_tag_counter: Counter[str] = Counter()
    project_dir_tag_counter: Counter[str] = Counter()

    for asset in library_assets:
        meta = _asset_meta(asset)
        provider = str(meta.get("provider") or "").strip().lower()
        rel = str(asset.rel_path or "")
        exists = _asset_exists(asset)
        item = {
            "id": int(asset.id or 0),
            "kind": str(asset.kind or ""),
            "rel_path": rel,
            "provider": provider,
            "created_at": str(getattr(asset, "created_at", "") or ""),
        }
        if not exists:
            invalid_library.append(item)
        if provider in {"pexels", "pixabay", "wikimedia", "douyin"}:
            suspicious_library.append(item)

    for asset in project_assets:
        tag = str(asset.tag or "").strip() or "<empty>"
        project_tag_counter[tag] += 1
        rel = str(asset.rel_path or "")
        if rel.startswith("library/"):
            project_assets_in_library_path.append(
                {
                    "id": int(asset.id or 0),
                    "project_id": int(asset.project_id or 0),
                    "project_title": titles.get(int(asset.project_id or 0), ""),
                    "tag": tag,
                    "rel_path": rel,
                }
            )
        if rel.startswith("project_"):
            project_dir_tag_counter[tag] += 1

    bound_library_ids = [int(a.id or 0) for a in bound_library_assets if getattr(a, "id", None) is not None]

    report = {
        "summary": {
            "library_asset_count": len(library_assets),
            "invalid_library_asset_count": len(invalid_library),
            "suspicious_library_asset_count": len(suspicious_library),
            "directly_bound_library_asset_count": len(bound_library_ids),
            "project_asset_count": len(project_assets),
            "project_assets_in_library_path_count": len(project_assets_in_library_path),
        },
        "library_provider_counter": dict(Counter(str(_asset_meta(a).get("provider") or "").strip().lower() or "<empty>" for a in library_assets)),
        "project_asset_tag_counter": dict(project_tag_counter),
        "project_dir_tag_counter": dict(project_dir_tag_counter),
        "directly_bound_library_asset_ids": bound_library_ids,
        "invalid_library_assets": invalid_library,
        "suspicious_library_assets": suspicious_library,
        "project_assets_in_library_path": project_assets_in_library_path,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
