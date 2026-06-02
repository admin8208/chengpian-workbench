import json
import re
from pathlib import Path

from sqlmodel import select

from app.models import Scene
from app.time_utils import now_utc


def library_asset_allowed(*, asset, asset_scene_use_count: dict[int, int], last_library_asset_id: int | None, consecutive_library_reuse: int, max_library_asset_reuse: int, max_library_consecutive_reuse: int) -> bool:
    if asset.id is None:
        return False
    asset_id = int(asset.id)
    used_count = int(asset_scene_use_count.get(asset_id, 0) or 0)
    if used_count >= max_library_asset_reuse:
        return False
    if last_library_asset_id == asset_id and consecutive_library_reuse >= max_library_consecutive_reuse:
        return False
    return True


def pick_main_library_hit(*, hits: list[tuple[object, dict, float]], expected_dur: float, main_clip_threshold, main_asset_ids: set[int], max_main_asset_count: int, asset_duration_sec) -> tuple[object, dict, float] | None:
    threshold = main_clip_threshold(float(expected_dur or 0.0))
    for asset, meta, score in hits:
        if str(getattr(asset, "kind", "") or "").strip().lower() != "video":
            continue
        if asset.id is None:
            continue
        if int(asset.id) in main_asset_ids:
            continue
        if len(main_asset_ids) >= max_main_asset_count:
            continue
        duration_sec = asset_duration_sec(asset, meta)
        if duration_sec >= threshold:
            return (asset, meta, score)
    return None


def pick_main_web_item(*, items: list, expected_dur: float, main_clip_threshold):
    threshold = main_clip_threshold(float(expected_dur or 0.0))
    for item in items:
        if str(getattr(item, "kind", "") or "").strip().lower() != "video":
            continue
        try:
            duration_sec = float(getattr(item, "duration_sec", 0.0) or 0.0)
        except Exception:
            duration_sec = 0.0
        if duration_sec >= threshold:
            return item
    return None


def search_library_assets(*, one_q: str, clean_query, library_rows: list[tuple[object, dict, str, str]], used_library_ids: set[int], allow_asset, used_title_keys: set[str], prefer: str) -> list[tuple[object, dict, float]]:
    query_low = clean_query(one_q).lower()
    if not query_low or not library_rows:
        return []
    tokens = [token for token in re.split(r"\s+", query_low) if token][:6]
    out: list[tuple[object, dict, float]] = []
    for asset, meta, hay, title_key in library_rows:
        if asset.id is None or int(asset.id) in used_library_ids:
            continue
        if not allow_asset(asset):
            continue
        if title_key and title_key in used_title_keys:
            continue
        score = 0.0
        provider = str(meta.get("provider") or "").strip().lower()
        asset_kind = str(getattr(asset, "kind", "") or "").strip().lower()
        if prefer == "video":
            score += 0.9 if asset_kind == "video" else 0.05
        else:
            score += 0.55 if asset_kind == "image" else 0.08
        if query_low and query_low in hay:
            score += 1.1
        for token in tokens:
            if token and token in hay:
                score += 0.28
        if provider == "pexels":
            score += 0.22
        elif provider == "pixabay":
            score += 0.14
        elif provider == "wikimedia":
            score += 0.05
        if score >= 1.0:
            out.append((asset, meta, score))
    out.sort(key=lambda item: item[2], reverse=True)
    return out[:6]


def record_failed_scene(*, failed_scene_reasons: list[dict[str, object]], scene_id: int, scene_idx: int, reason_code: str, reason_label: str, query_used: str, provider: str = "", detail: str = "", session_scope) -> None:
    failed_scene_reasons.append(
        {
            "scene_id": int(scene_id),
            "scene_idx": int(scene_idx),
            "reason_code": str(reason_code or "unknown"),
            "reason_label": str(reason_label or "素材补齐失败"),
            "query_used": str(query_used or "")[:120],
            "provider": str(provider or "")[:40],
            "detail": str(detail or "")[:220],
        }
    )
    try:
        with session_scope() as session:
            scene = session.exec(select(Scene).where(Scene.id == int(scene_id))).first()
            if not scene:
                return
            meta = json.loads(getattr(scene, "meta_json", "{}") or "{}")
            if not isinstance(meta, dict):
                meta = {}
            meta.setdefault("search", {})
            if isinstance(meta.get("search"), dict):
                meta["search"]["failed_reason_code"] = str(reason_code or "unknown")
                meta["search"]["failed_reason_label"] = str(reason_label or "素材补齐失败")
                meta["search"]["failed_provider"] = str(provider or "")[:40]
                meta["search"]["failed_query"] = str(query_used or "")[:120]
            scene.meta_json = json.dumps(meta, ensure_ascii=True)
            scene.updated_at = now_utc()
            session.add(scene)
    except Exception:
        pass


def set_scene_asset(*, scene_id: int, asset_id: int, query_used: str, best_conf: float, best_reason: str, source_label: str, render_role: str = "support", segment_start: float | None = None, segment_end: float | None = None, session_scope) -> None:
    with session_scope() as session:
        scene = session.exec(select(Scene).where(Scene.id == scene_id)).first()
        if not scene:
            return
        scene.image_asset_id = int(asset_id)
        scene.status = "ready"
        try:
            meta = json.loads(getattr(scene, "meta_json", "{}") or "{}")
            if not isinstance(meta, dict):
                meta = {}
            meta.pop("needs_review", None)
            meta["media_pipeline"] = "network_asset"
            meta["binding_material_mode"] = "network"
            meta["project_material_mode"] = "network"
            meta["bound_asset_material_mode"] = "network"
            meta.setdefault("search", {})
            meta.setdefault("render", {})
            if isinstance(meta.get("search"), dict):
                meta["search"].pop("needs_review", None)
                meta["search"].pop("confirmed_at", None)
                if query_used:
                    meta["search"]["last_query"] = str(query_used)[:120]
                if best_conf:
                    meta["search"]["best_confidence"] = float(best_conf or 0.0)
                if best_reason:
                    meta["search"]["llm_reason"] = str(best_reason)[:260]
                if source_label:
                    meta["search"]["source"] = source_label
            if isinstance(meta.get("render"), dict):
                if segment_start is not None:
                    meta["render"]["clip_start_sec"] = float(segment_start)
                else:
                    meta["render"].pop("clip_start_sec", None)
                if segment_end is not None:
                    meta["render"]["clip_end_sec"] = float(segment_end)
                else:
                    meta["render"].pop("clip_end_sec", None)
                meta["render"]["role"] = str(render_role or "support")
            scene.meta_json = json.dumps(meta, ensure_ascii=True)
        except Exception:
            pass
        scene.updated_at = now_utc()
        session.add(scene)
