from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import select

from app.db import session_scope
from app.jobs import is_job_cancelled, patch_job_payload, update_job, wait_if_job_paused
from app.llm_service import get_api_key, get_default_provider
from app.models import Asset, Project, Scene
from app.modules.media.library_import import ImportRequest, import_to_project
from app.modules.media.service import get_media_api_key, has_media_api_key
from app.modules.media.web_search import search_web_media, search_web_media_parallel, supported_providers
from app.project_paths import asset_disk_path
from app.settings import settings
from app.tasks_helpers import classify_media_provider_error as classify_media_provider_error_local
from app.tasks_media_binding import (
    library_asset_allowed as library_asset_allowed_helper,
    pick_main_library_hit as pick_main_library_hit_helper,
    pick_main_web_item as pick_main_web_item_helper,
    record_failed_scene as record_failed_scene_helper,
    search_library_assets as search_library_assets_helper,
    set_scene_asset as set_scene_asset_helper,
)
from app.tasks_media_bridge import autofill_media_local_bridge
from app.tasks_media_import_flow import apply_imported_asset, import_candidate_assets
from app.tasks_media_queries import build_query_candidates as build_query_candidates_helper, clean_query as clean_query_helper, llm_extra_queries as llm_extra_queries_helper, looks_english as looks_english_helper
from app.tasks_media_rewrite import rewrite_to_en_keywords as rewrite_to_en_keywords_helper
from app.tasks_media_runtime import autofill_media_impl_runtime
from app.tasks_media_scene_flow import retry_scene_candidates, search_scene_candidates
from app.tasks_media_search import llm_pick_best as llm_pick_best_helper, mark_provider_failure as mark_provider_failure_helper, rank_items as rank_items_helper, search_all as search_all_helper, search_images_only as search_images_only_helper
from app.time_utils import now_utc
from app.material_policies import project_material_mode


def get_role_asset_path_local(session, project: Project) -> Path | None:
    if not project.role_image_asset_id:
        return None
    asset = session.exec(select(Asset).where(Asset.id == project.role_image_asset_id)).first()
    if not asset:
        return None
    path = asset_disk_path(str(asset.rel_path or ""), is_export=False)
    return path if path.exists() else None


def get_project_media_plan_local(session, project_id: int) -> list[tuple[int, int, str, str, float, str]]:
    rows = session.exec(
        select(Scene)
        .where(Scene.project_id == int(project_id))
        .order_by(Scene.idx)
    ).all()
    plan: list[tuple[int, int, str, str, float, str]] = []
    for sc in rows:
        if getattr(sc, "image_asset_id", None):
            continue
        scene_id = int(getattr(sc, "id", 0) or 0)
        if scene_id <= 0:
            continue
        scene_idx = int(getattr(sc, "idx", 0) or 0)
        narration = str(getattr(sc, "narration", "") or "").strip()
        media_query = str(getattr(sc, "media_query", "") or "").strip()[:120]
        if not media_query:
            media_query = narration[:120]
        try:
            expected_dur = max(2.0, float(getattr(sc, "duration_sec", 0.0) or 0.0))
        except Exception:
            expected_dur = 4.0
        meta_json = str(getattr(sc, "meta_json", "") or "{}")
        try:
            meta_obj = json.loads(meta_json)
            if not isinstance(meta_obj, dict):
                meta_obj = {}
        except Exception:
            meta_obj = {}
        plan.append((scene_id, scene_idx, media_query, narration, expected_dur, json.dumps(meta_obj, ensure_ascii=True)))
    return plan


def autofill_media_impl_local(
    job_id: int,
    project_id: int,
    prefer: str = "video",
    *,
    outer_job_id: int | None = None,
    progress_base: int = 0,
    progress_span: int = 100,
    keep_running: bool = False,
) -> None:
    return autofill_media_impl_runtime(
        job_id,
        project_id,
        prefer=prefer,
        outer_job_id=outer_job_id,
        progress_base=progress_base,
        progress_span=progress_span,
        keep_running=keep_running,
        update_job=update_job,
        clean_query_helper=clean_query_helper,
        looks_english_helper=looks_english_helper,
        session_scope=session_scope,
        get_role_asset_path=get_role_asset_path_local,
        import_to_project=import_to_project,
        import_request_cls=ImportRequest,
        get_project_media_plan=get_project_media_plan_local,
        supported_providers=supported_providers,
        has_media_api_key=has_media_api_key,
        get_media_api_key=get_media_api_key,
        get_default_provider=get_default_provider,
        get_api_key=get_api_key,
        now_utc=now_utc,
        search_web_media_parallel=search_web_media_parallel,
        search_web_media=search_web_media,
        mark_provider_failure_helper=mark_provider_failure_helper,
        record_failed_scene_helper=record_failed_scene_helper,
        set_scene_asset_helper=set_scene_asset_helper,
        library_asset_allowed_helper=library_asset_allowed_helper,
        pick_main_library_hit_helper=pick_main_library_hit_helper,
        pick_main_web_item_helper=pick_main_web_item_helper,
        search_library_assets_helper=search_library_assets_helper,
        rank_items_helper=rank_items_helper,
        llm_pick_best_helper=llm_pick_best_helper,
        search_all_helper=search_all_helper,
        search_images_only_helper=search_images_only_helper,
        rewrite_to_en_keywords_helper=rewrite_to_en_keywords_helper,
        search_scene_candidates=search_scene_candidates,
        retry_scene_candidates=retry_scene_candidates,
        import_candidate_assets=import_candidate_assets,
        apply_imported_asset=apply_imported_asset,
        build_query_candidates_helper=build_query_candidates_helper,
        llm_extra_queries=llm_extra_queries_helper,
        classify_media_provider_error=classify_media_provider_error_local,
        patch_job_payload=patch_job_payload,
        wait_if_job_paused=wait_if_job_paused,
        is_job_cancelled=is_job_cancelled,
        settings=settings,
    )


def autofill_media_local(
    job_id: int,
    project_id: int,
    prefer: str = "video",
    *,
    outer_job_id: int | None = None,
    progress_base: int = 0,
    progress_span: int = 100,
    keep_running: bool = False,
) -> None:
    autofill_media_local_bridge(
        job_id,
        project_id,
        prefer=prefer,
        outer_job_id=outer_job_id,
        progress_base=progress_base,
        progress_span=progress_span,
        keep_running=keep_running,
        media_impl=autofill_media_impl_local,
    )


__all__ = [
    "get_role_asset_path_local",
    "get_project_media_plan_local",
    "autofill_media_impl_local",
    "autofill_media_local",
]
