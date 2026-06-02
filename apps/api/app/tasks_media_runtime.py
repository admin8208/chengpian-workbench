import json
import random
import re
import time
from pathlib import Path

from loguru import logger
from sqlmodel import select

from app.logging_setup import sanitize_log_text
from app.models import Asset, Project, Scene


def _coerce_plan_duration(raw_value, *, scene_id: int, scene_idx: int) -> float:
    try:
        dur = float(raw_value or 0.0)
    except Exception:
        logger.warning(
            "media plan invalid duration; fallback to 4.0 | scene_id={} scene_idx={} raw_value={!r}",
            scene_id,
            scene_idx,
            raw_value,
        )
        return 4.0
    if dur <= 0:
        logger.warning(
            "media plan non-positive duration; fallback to 4.0 | scene_id={} scene_idx={} raw_value={!r}",
            scene_id,
            scene_idx,
            raw_value,
        )
        return 4.0
    return max(2.0, dur)


def autofill_media_impl_runtime(
    job_id: int,
    project_id: int,
    prefer: str = "video",
    *,
    outer_job_id: int | None = None,
    progress_base: int = 0,
    progress_span: int = 100,
    keep_running: bool = False,
    update_job,
    clean_query_helper,
    looks_english_helper,
    session_scope,
    get_role_asset_path,
    import_to_project,
    import_request_cls,
    get_project_media_plan,
    supported_providers,
    has_media_api_key,
    get_media_api_key,
    get_default_provider,
    get_api_key,
    now_utc,
    search_web_media_parallel,
    search_web_media,
    mark_provider_failure_helper,
    record_failed_scene_helper,
    set_scene_asset_helper,
    library_asset_allowed_helper,
    pick_main_library_hit_helper,
    pick_main_web_item_helper,
    search_library_assets_helper,
    rank_items_helper,
    llm_pick_best_helper,
    search_all_helper,
    search_images_only_helper,
    rewrite_to_en_keywords_helper,
    search_scene_candidates,
    retry_scene_candidates,
    import_candidate_assets,
    apply_imported_asset,
    build_query_candidates_helper,
    llm_extra_queries,
    classify_media_provider_error,
    patch_job_payload,
    wait_if_job_paused,
    is_job_cancelled,
    settings,
) -> None:
    target_job_id = int(outer_job_id) if outer_job_id else int(job_id)

    def _scale(p: int | None) -> int | None:
        if p is None:
            return None
        try:
            p2 = max(0, min(100, int(p)))
        except Exception:
            return None
        try:
            b = int(progress_base)
            s = int(progress_span)
        except Exception:
            b, s = 0, 100
        b = max(0, min(100, b))
        s = max(0, min(100, s))
        return max(0, min(100, b + int(p2 * (s / 100.0))))

    def _upd(*, status: str | None = None, progress: int | None = None, message: str | None = None) -> None:
        st = status
        if keep_running and st == "done":
            st = None
        update_job(target_job_id, status=st, progress=_scale(progress), message=message if message is not None else "")

    if keep_running and outer_job_id:
        _upd(status="running", progress=0, message="")

    prefer = (prefer or "video").strip().lower()
    if prefer not in ("video", "image"):
        prefer = "video"

    def _clean_query(q: str) -> str:
        return clean_query_helper(q)

    def _looks_english(q: str) -> bool:
        return looks_english_helper(q)

    try:
        with session_scope() as session:
            project = session.exec(select(Project).where(Project.id == project_id)).first()
            if not project:
                _upd(status="failed", progress=100, message="项目不存在")
                return
            _ = get_role_asset_path(session, project)
            pid = int(project.id)
            plan = get_project_media_plan(session, project_id)
            track_key = str(project.channel_key or "")
            if not plan:
                _upd(status="done", progress=100, message="所有镜头已有素材，无需填充")
                return
            normalized_plan: list[tuple[int, int, str, str, float, str]] = []
            for raw in plan:
                try:
                    scene_id, scene_idx, q, narration, expected_dur, meta_json = raw
                except Exception:
                    logger.warning("media plan invalid row shape; skip row={!r}", raw)
                    continue
                scene_id = int(scene_id or 0)
                scene_idx = int(scene_idx or 0)
                q = str(q or "").strip()
                narration = str(narration or "").strip()
                meta_json = str(meta_json or "{}")
                expected_dur = _coerce_plan_duration(expected_dur, scene_id=scene_id, scene_idx=scene_idx)
                normalized_plan.append((scene_id, scene_idx, q, narration, expected_dur, meta_json))
            plan = normalized_plan
            if not plan:
                _upd(status="done", progress=100, message="所有镜头已有素材，无需填充")
                return

            tr = 9.0 / 16.0
            media_pick_mode = "smart"
            try:
                rcfg = project.render_config() if hasattr(project, "render_config") else {}
                if isinstance(rcfg, dict):
                    media_pick_mode = str(rcfg.get("media_pick_mode") or "smart").strip().lower() or "smart"
                    if media_pick_mode not in ("smart", "random_video"):
                        media_pick_mode = "smart"
                    aspect = str(rcfg.get("aspect") or "").strip().lower()
                    if aspect == "landscape":
                        tr = 16.0 / 9.0
                    else:
                        w = rcfg.get("width")
                        h = rcfg.get("height")
                        if w is not None and h is not None:
                            try:
                                ww = float(w)
                                hh = float(h)
                                if ww > 0 and hh > 0:
                                    tr = ww / hh
                            except Exception:
                                pass
            except Exception:
                pass

        total = len(plan)
        if total <= 0:
            _upd(status="done", progress=100, message="所有镜头已有素材，无需填充")
            return

        provider_order = [p for p in ["pexels", "pixabay", "wikimedia"] if p in supported_providers()]
        provider_keys: dict[str, str] = {"wikimedia": ""}
        with session_scope() as session:
            for p in provider_order:
                if p == "wikimedia":
                    continue
                if has_media_api_key(session, p):
                    provider_keys[p] = get_media_api_key(session, p)

        active_providers = [p for p in provider_order if (p == "wikimedia" or provider_keys.get(p))]
        if not active_providers:
            active_providers = ["wikimedia"]

        llm_cfg: dict | None = None
        llm_cache: dict[str, list[str]] = {}
        with session_scope() as session:
            prov = get_default_provider(session)
            if prov and prov.enabled and prov.default_model and prov.base_url:
                key = ""
                if prov.type == "openai_compat" and prov.id is not None:
                    key = get_api_key(session, int(prov.id))
                if prov.type == "ollama" or (prov.type == "openai_compat" and key):
                    llm_cfg = {"type": prov.type, "base_url": prov.base_url, "model": prov.default_model, "api_key": key}

        filled = 0
        errors: list[str] = []
        search_errors = 0
        import_errors = 0
        timed_out_scenes = 0
        provider_fail_counts: dict[str, int] = {}
        provider_blocked_until: dict[str, float] = {}
        provider_failure_events: list[dict[str, object]] = []
        failed_scene_reasons: list[dict[str, object]] = []
        project_title = ""
        with session_scope() as session:
            p2 = session.exec(select(Project).where(Project.id == project_id)).first()
            project_title = (p2.title or "").strip() if p2 else ""

        from app.modules.media.wikimedia import url_hash

        scene_soft_timeout_s = 42 if keep_running else 55
        search_timeout_s = 12 if keep_running else 30
        media_total_deadline = time.time() + (260 if keep_running else 480)

        used_hashes: set[str] = set()
        used_title_keys: set[str] = set()
        used_library_ids: set[int] = set()
        recent_providers: list[str] = []
        library_rows: list[tuple[Asset, dict, str, str]] = []
        current_main_asset_id: int | None = None
        current_main_duration_sec = 0.0
        current_main_remaining_sec = 0.0
        current_main_cursor_sec = 0.0
        main_asset_ids: set[int] = set()
        total_expected_dur = float(sum(float(x[4] or 0.0) for x in plan))
        prefer_single_main = bool(prefer == "video" and total >= 3)
        main_clip_min_duration_sec = max(10.0, min(24.0, total_expected_dur / 4.0))
        max_main_asset_count = 2
        max_main_consecutive_scenes = 4
        max_main_scene_share = 0.72
        max_library_asset_reuse = 1
        max_library_consecutive_reuse = 0
        asset_scene_use_count: dict[int, int] = {}
        current_main_consecutive = 0
        asset_duration_cache: dict[str, float] = {}
        last_library_asset_id: int | None = None
        consecutive_library_reuse = 0

        def _library_asset_allowed(asset: Asset) -> bool:
            return library_asset_allowed_helper(
                asset=asset,
                asset_scene_use_count=asset_scene_use_count,
                last_library_asset_id=last_library_asset_id,
                consecutive_library_reuse=consecutive_library_reuse,
                max_library_asset_reuse=max_library_asset_reuse,
                max_library_consecutive_reuse=max_library_consecutive_reuse,
            )

        def _main_clip_threshold(expected_dur: float) -> float:
            if prefer_single_main:
                if len(main_asset_ids) <= 0:
                    return max(main_clip_min_duration_sec, min(48.0, float(expected_dur or 0.0) * 1.8))
                return max(8.0, min(28.0, float(expected_dur or 0.0) * 1.25))
            return max(main_clip_min_duration_sec, float(expected_dur or 0.0) * 1.6)

        def _main_clip_window(*, duration_sec: float, expected_dur: float, scene_idx: int) -> tuple[float | None, float | None]:
            dur = max(0.0, float(duration_sec or 0.0))
            need = max(1.8, float(expected_dur or 0.0) + 0.18)
            if dur <= 0.0 or dur <= need + 0.08:
                return (None, None)
            start = max(0.0, float(current_main_cursor_sec or 0.0))
            if start + need > dur:
                start = max(0.0, dur - need - 0.02)
            end = min(dur, start + need)
            if end - start < 0.8:
                return (None, None)
            return (round(start, 3), round(end, 3))

        def _title_key(s: str) -> str:
            t = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", str(s or "").lower())
            t = re.sub(r"\s{2,}", " ", t).strip()
            return t[:48]

        def _asset_title_key(asset: Asset, meta: dict | None = None) -> str:
            meta2 = meta if isinstance(meta, dict) else {}
            title = str(meta2.get("title") or "").strip()
            if title:
                return _title_key(title)
            rel = str(getattr(asset, "rel_path", "") or "")
            stem = Path(rel).stem if rel else ""
            return _title_key(stem)

        def _probe_video_duration_cached(path: Path) -> float:
            key = str(path.resolve())
            if key in asset_duration_cache:
                return asset_duration_cache[key]
            try:
                from moviepy import VideoFileClip as _VF

                clip = _VF(str(path))
                dur = float(getattr(clip, "duration", 0.0) or 0.0)
                try:
                    clip.close()
                except Exception:
                    pass
            except Exception:
                dur = 0.0
            asset_duration_cache[key] = dur
            return dur

        def _asset_duration_sec(asset: Asset, meta: dict | None = None) -> float:
            meta2 = meta if isinstance(meta, dict) else {}
            try:
                dur = float(meta2.get("duration_sec") or 0.0)
                if dur > 0:
                    return dur
            except Exception:
                pass
            try:
                rel = str(getattr(asset, "rel_path", "") or "").strip()
                if rel:
                    p = (settings.assets_dir / rel.lstrip("/")).resolve()
                    if p.exists() and p.is_file():
                        return _probe_video_duration_cached(p)
            except Exception:
                pass
            return 0.0

        def _pick_main_library_hit(hits: list[tuple[Asset, dict, float]], expected_dur: float):
            return pick_main_library_hit_helper(hits=hits, expected_dur=expected_dur, main_clip_threshold=_main_clip_threshold, main_asset_ids=main_asset_ids, max_main_asset_count=max_main_asset_count, asset_duration_sec=_asset_duration_sec)

        def _pick_main_web_item(items: list, expected_dur: float):
            return pick_main_web_item_helper(items=items, expected_dur=expected_dur, main_clip_threshold=_main_clip_threshold)

        try:
            with session_scope() as session:
                rows = session.exec(select(Asset).where(Asset.tag == "library").where(Asset.kind.in_(["image", "video"])).order_by(Asset.created_at.desc()).limit(500)).all()
                for asset in rows:
                    if asset.id is None:
                        continue
                    try:
                        meta = json.loads(getattr(asset, "meta_json", "{}") or "{}")
                        if not isinstance(meta, dict):
                            meta = {}
                    except Exception:
                        meta = {}
                    hay = " ".join([str(meta.get("title") or ""), str(meta.get("author") or ""), str(meta.get("provider") or ""), str(meta.get("attribution") or ""), str(getattr(asset, "rel_path", "") or "")]).lower()
                    library_rows.append((asset, meta, hay, _asset_title_key(asset, meta)))
        except Exception:
            library_rows = []

        def _search_library_assets(one_q: str):
            if skip_library_reuse:
                return []
            return search_library_assets_helper(one_q=one_q, clean_query=_clean_query, library_rows=library_rows, used_library_ids=used_library_ids, allow_asset=_library_asset_allowed, used_title_keys=used_title_keys, prefer=prefer)

        def _library_asset_file_exists(asset: Asset) -> bool:
            rel = str(getattr(asset, "rel_path", "") or "").strip()
            if not rel:
                return False
            try:
                return (settings.assets_dir / rel.lstrip("/")).resolve().is_file()
            except Exception:
                return False

        random_video_rows = [(asset, meta) for asset, meta, _hay, _title_key in library_rows if str(getattr(asset, "kind", "") or "").strip().lower() == "video" and getattr(asset, "id", None) is not None and _library_asset_file_exists(asset)]
        skip_library_reuse = bool(media_pick_mode == "random_video" and not random_video_rows)

        def _pick_random_library_video(*, scene_id: int, scene_idx: int, expected_dur: float, previous_asset_id: int | None) -> tuple[Asset, dict, float | None, float | None] | None:
            if not random_video_rows:
                return None
            rows = random_video_rows
            if len(rows) > 1 and previous_asset_id:
                rows = [(asset, meta) for asset, meta in rows if int(asset.id or 0) != int(previous_asset_id)] or rows
            min_use = min(int(asset_scene_use_count.get(int(asset.id or 0), 0) or 0) for asset, _meta in rows)
            least_used = [(asset, meta) for asset, meta in rows if int(asset_scene_use_count.get(int(asset.id or 0), 0) or 0) == min_use]
            rng = random.Random(f"random_video:{int(project_id)}:{int(scene_id)}:{int(scene_idx)}:{min_use}")
            asset, meta = rng.choice(least_used)
            dur = _asset_duration_sec(asset, meta)
            need = max(1.8, float(expected_dur or 0.0) + 0.18)
            if dur <= need + 0.08:
                return asset, meta, None, None
            max_start = max(0.0, float(dur) - need)
            seg_start = round(rng.uniform(0.0, max_start), 3) if max_start > 0 else 0.0
            seg_end = round(min(float(dur), seg_start + need), 3)
            return asset, meta, seg_start, seg_end

        def _mark_provider_failure(provider: str, detail: str, kind: str = "", query: str = "") -> None:
            mark_provider_failure_helper(provider=provider, detail=detail, provider_fail_counts=provider_fail_counts, provider_blocked_until=provider_blocked_until, classify_media_provider_error=classify_media_provider_error)
            if len(provider_failure_events) >= 20:
                return
            code, label = classify_media_provider_error(str(detail or ""))
            provider_failure_events.append(
                {
                    "provider": str(provider or "")[:40],
                    "kind": str(kind or "")[:20],
                    "query": str(query or "")[:120],
                    "reason_code": str(code or "unknown")[:60],
                    "reason_label": str(label or "素材源异常")[:80],
                    "detail": str(detail or "")[:220],
                }
            )

        def _record_failed_scene(*, scene_id: int, scene_idx: int, reason_code: str, reason_label: str, query_used: str, provider: str = "", detail: str = "") -> None:
            record_failed_scene_helper(failed_scene_reasons=failed_scene_reasons, scene_id=scene_id, scene_idx=scene_idx, reason_code=reason_code, reason_label=reason_label, query_used=query_used, provider=provider, detail=detail, session_scope=session_scope)

        def _set_scene_asset(*, scene_id: int, asset_id: int, query_used: str, best_conf: float, best_reason: str, source_label: str, render_role: str = "support", segment_start: float | None = None, segment_end: float | None = None) -> None:
            set_scene_asset_helper(scene_id=scene_id, asset_id=asset_id, query_used=query_used, best_conf=best_conf, best_reason=best_reason, source_label=source_label, render_role=render_role, segment_start=segment_start, segment_end=segment_end, session_scope=session_scope)

        def _human_shot_bias(title: str, query: str, provider: str) -> float:
            t = str(title or "").lower()
            q = str(query or "").lower()
            score = 0.0
            life_tracks = {"emotion", "career", "family_cn"}
            noisy_pixabay_terms = (
                "mosquito",
                "insect",
                "dengue",
                "snail",
                "otter",
                "football table",
                "beach",
                "coast",
                "ocean",
                "seascape",
                "sunset",
                "sunrise",
                "sea ",
                "nature",
                "animal",
                "zoo",
                "flower",
                "landscape",
            )
            if provider == "wikimedia" and track_key in life_tracks:
                score -= 0.65
            if provider == "pexels" and track_key in life_tracks:
                score += 0.18
            if provider == "pixabay" and track_key in life_tracks:
                score -= 0.08
                for term in noisy_pixabay_terms:
                    if term in t and term.strip() not in q:
                        score -= 0.72
                        break
            if track_key == "history":
                if re.search(r"(ancient|historical|palace|temple|map|document|scroll|artifact|statue)", t):
                    score += 0.45
                if re.search(r"(close up|detail|old|stone|paper|archive)", t):
                    score += 0.16
            elif track_key == "emotion":
                if re.search(r"(alone|lonely|couple|argument|hug|cry|window|night|chat|message|silhouette)", t):
                    score += 0.42
                if re.search(r"(close up|face|hands|back view|waiting|street)", t):
                    score += 0.18
            elif track_key == "family_cn":
                if re.search(r"(family|dinner|parents|mother|father|home|living room|phone call|table)", t):
                    score += 0.42
                if re.search(r"(close up|kitchen|apartment|window|hallway)", t):
                    score += 0.15
            else:
                if re.search(r"(office|meeting|laptop|desk|commute|elevator|message|presentation|work)", t):
                    score += 0.40
                if re.search(r"(close up|typing|corridor|overtime|subway|coffee)", t):
                    score += 0.16
            if re.search(r"(abstract|illustration|cartoon|vector|background|wallpaper)", t):
                score -= 0.45
            if provider == "wikimedia" and track_key in ("emotion", "career", "family_cn"):
                score -= 0.08
            if provider in ("pexels", "pixabay") and track_key == "history":
                score -= 0.04
            if any(x in q for x in ("night", "alone", "meeting", "family", "ancient")) and any(x in t for x in ("night", "alone", "meeting", "family", "ancient")):
                score += 0.12
            return score

        used_asset_types = []
        used_providers = []

        def _rank_items(*, items: list, expected_dur: float, query: str, scene_meta: dict | None = None, prev_scene_meta: dict | None = None) -> list:
            return rank_items_helper(items=items, expected_dur=expected_dur, query=query, scene_meta=scene_meta, prev_scene_meta=prev_scene_meta, pack_key=track_key, tr=tr, prefer=prefer, used_asset_types=used_asset_types, used_providers=used_providers, human_shot_bias=_human_shot_bias)

        def _llm_pick_best(*, narration: str, query: str, items: list) -> tuple[int, float, str]:
            return llm_pick_best_helper(llm_cfg=llm_cfg, narration=narration, query=query, items=items)

        def _search_all(one_q: str) -> list:
            return search_all_helper(query=one_q, prefer=prefer, active_providers=active_providers, provider_blocked_until=provider_blocked_until, provider_keys=provider_keys, media_total_deadline=media_total_deadline, search_timeout_s=search_timeout_s, target_aspect=tr, search_web_media_parallel=search_web_media_parallel, search_web_media=search_web_media, mark_provider_failure_cb=_mark_provider_failure)

        def _search_images_only(one_q: str) -> list:
            return search_images_only_helper(query=one_q, active_providers=active_providers, provider_blocked_until=provider_blocked_until, provider_keys=provider_keys, media_total_deadline=media_total_deadline, search_timeout_s=search_timeout_s, target_aspect=tr, search_web_media_parallel=search_web_media_parallel, search_web_media=search_web_media, mark_provider_failure_cb=_mark_provider_failure)

        common_chinese_keywords = {"人物": "people", "自然": "nature", "城市": "city", "科技": "technology", "商业": "business", "教育": "education", "健康": "health", "娱乐": "entertainment", "体育": "sports", "旅行": "travel", "美食": "food", "家庭": "family", "工作": "work", "学习": "learning", "爱情": "love", "友情": "friendship", "成功": "success", "失败": "failure", "希望": "hope", "梦想": "dream", "挑战": "challenge", "成长": "growth"}
        en_rewrite_cache: dict[str, str] = {}

        def _rewrite_to_en_keywords(q: str) -> str:
            return rewrite_to_en_keywords_helper(query=q, clean_query=_clean_query, looks_english=_looks_english, llm_cfg=llm_cfg, en_rewrite_cache=en_rewrite_cache, common_chinese_keywords=common_chinese_keywords)

        prev_scene_meta_for_rank: dict | None = None
        for i, (scene_id, scene_idx, q, narration, expected_dur, meta_json) in enumerate(plan, start=1):
            wait_if_job_paused(target_job_id)
            if is_job_cancelled(target_job_id):
                _upd(status="cancelled", progress=100, message="已取消")
                return
            if time.time() >= media_total_deadline:
                if len(errors) < 5:
                    errors.append(f"镜头 {scene_idx} 超时：自动填充已提前收口")
                timed_out_scenes += 1
                break
            scene_deadline = time.time() + scene_soft_timeout_s
            web_items = []
            last_search_err: Exception | None = None
            scene_meta: dict = {}
            try:
                scene_meta = json.loads(meta_json or "{}")
                if not isinstance(scene_meta, dict):
                    scene_meta = {}
            except Exception:
                scene_meta = {}
            prev_scene_meta = prev_scene_meta_for_rank if isinstance(prev_scene_meta_for_rank, dict) else None
            scene_continuity_jump = bool(((scene_meta.get("continuity") or {}).get("jump_from_prev")) if isinstance(scene_meta.get("continuity"), dict) else False)
            remaining_expected_dur = float(sum(float(x[4] or 0.0) for x in plan[i - 1:]))
            if prefer_single_main and max_main_asset_count < 2 and len(main_asset_ids) >= 1:
                if float(current_main_remaining_sec or 0.0) + 2.0 < remaining_expected_dur * 0.72:
                    max_main_asset_count = 2
            candidates = build_query_candidates_helper(media_query=q, narration=narration, title=project_title, pack_key=str(track_key), scene_meta=scene_meta, prev_scene_meta=prev_scene_meta)
            if media_pick_mode == "random_video" and random_video_rows:
                random_pick = _pick_random_library_video(scene_id=scene_id, scene_idx=scene_idx, expected_dur=float(expected_dur or 0.0), previous_asset_id=last_library_asset_id)
                if random_pick is not None:
                    try:
                        random_asset, random_meta, seg_start, seg_end = random_pick
                        aid = int(random_asset.id or 0)
                        if aid > 0:
                            _set_scene_asset(scene_id=scene_id, asset_id=aid, query_used="", best_conf=0.0, best_reason="", source_label="random_library_video", render_role="support", segment_start=seg_start, segment_end=seg_end)
                            used_library_ids.add(aid)
                            tk2 = _asset_title_key(random_asset, random_meta)
                            if tk2:
                                used_title_keys.add(tk2)
                            asset_scene_use_count[aid] = int(asset_scene_use_count.get(aid, 0) or 0) + 1
                            if last_library_asset_id == aid:
                                consecutive_library_reuse += 1
                            else:
                                last_library_asset_id = aid
                                consecutive_library_reuse = 1
                            current_main_consecutive = 0
                            filled += 1
                            prev_scene_meta_for_rank = scene_meta
                            _upd(progress=min(95, 2 + int(i / total * 90)), message=f"已随机绑定素材库视频 {filled}/{total}：镜头 {scene_idx}")
                            continue
                    except Exception as exc:
                        logger.warning("random library video pick failed; fallback smart fill | project_id={} scene_id={} err={!r}", project_id, scene_id, exc)
            can_continue_main = bool(current_main_asset_id and current_main_remaining_sec >= max(1.6, float(expected_dur or 0.0) * 0.72))
            if can_continue_main and current_main_asset_id:
                used_n = int(asset_scene_use_count.get(int(current_main_asset_id), 0) or 0)
                next_share = float(used_n + 1) / float(max(1, total))
                if current_main_consecutive >= max_main_consecutive_scenes or next_share > max_main_scene_share:
                    can_continue_main = False
            if can_continue_main:
                try:
                    seg_start, seg_end = _main_clip_window(duration_sec=float(current_main_duration_sec or 0.0), expected_dur=float(expected_dur or 0.0), scene_idx=scene_idx)
                    _set_scene_asset(scene_id=scene_id, asset_id=int(current_main_asset_id), query_used=q, best_conf=0.0, best_reason="", source_label="mixed_main_timeline", render_role="main", segment_start=seg_start, segment_end=seg_end)
                    current_main_remaining_sec = max(0.0, float(current_main_remaining_sec) - float(expected_dur or 0.0))
                    if seg_end is not None:
                        current_main_cursor_sec = max(float(current_main_cursor_sec or 0.0), float(seg_end) - 0.12)
                    aid = int(current_main_asset_id)
                    asset_scene_use_count[aid] = int(asset_scene_use_count.get(aid, 0) or 0) + 1
                    current_main_consecutive += 1
                    filled += 1
                    prev_scene_meta_for_rank = scene_meta
                    _upd(progress=min(95, 2 + int(i / total * 90)), message=f"已从长视频主素材连续切片 {filled}/{total}：镜头 {scene_idx}")
                    continue
                except Exception:
                    pass
            query_used = ""
            library_pick: Asset | None = None
            library_pick_meta: dict = {}
            picked_main_candidate = False
            main_candidate_file_url = ""
            main_candidate_duration_sec = 0.0
            want_new_main_clip = bool(prefer_single_main and len(main_asset_ids) < max_main_asset_count and (current_main_asset_id is None or float(current_main_remaining_sec or 0.0) < max(2.0, float(expected_dur or 0.0) * 0.92)))
            first_pass = search_scene_candidates(candidates=candidates, prefer=prefer, want_new_main_clip=want_new_main_clip, remaining_expected_dur=remaining_expected_dur, expected_dur=float(expected_dur or 0.0), scene_meta=scene_meta, scene_deadline=scene_deadline, media_total_deadline=media_total_deadline, now_time=time.time, search_all=_search_all, search_images_only=_search_images_only, rank_items=_rank_items, pick_main_web_item=_pick_main_web_item, search_library_assets=_search_library_assets, pick_main_library_hit=_pick_main_library_hit)
            web_items = first_pass.web_items or []
            query_used = first_pass.query_used
            library_pick = first_pass.library_pick if isinstance(first_pass.library_pick, Asset) else first_pass.library_pick
            library_pick_meta = first_pass.library_pick_meta or {}
            picked_main_candidate = first_pass.picked_main_candidate
            main_candidate_file_url = first_pass.main_candidate_file_url
            main_candidate_duration_sec = first_pass.main_candidate_duration_sec
            if first_pass.last_search_err is not None:
                last_search_err = first_pass.last_search_err
            if library_pick and library_pick.id is not None:
                try:
                    library_role = "main" if picked_main_candidate and str(getattr(library_pick, "kind", "") or "").lower() == "video" else "support"
                    library_dur = _asset_duration_sec(library_pick, library_pick_meta)
                    if not _library_asset_allowed(library_pick):
                        library_pick = None
                        raise RuntimeError("library_reuse_limit")
                    seg_start = None
                    seg_end = None
                    if library_role == "main":
                        seg_start, seg_end = _main_clip_window(duration_sec=float(library_dur or 0.0), expected_dur=float(expected_dur or 0.0), scene_idx=scene_idx)
                    _set_scene_asset(scene_id=scene_id, asset_id=int(library_pick.id), query_used=query_used, best_conf=0.0, best_reason="", source_label="library_reuse", render_role=library_role, segment_start=seg_start, segment_end=seg_end)
                    used_library_ids.add(int(library_pick.id))
                    tk2 = _asset_title_key(library_pick, library_pick_meta)
                    if tk2:
                        used_title_keys.add(tk2)
                    prov3 = str(library_pick_meta.get("provider") or "").strip()
                    if prov3:
                        recent_providers.append(prov3)
                        if len(recent_providers) > 4:
                            recent_providers[:] = recent_providers[-4:]
                    if library_role == "main":
                        current_main_asset_id = int(library_pick.id)
                        current_main_duration_sec = float(library_dur or 0.0)
                        current_main_remaining_sec = max(0.0, float(library_dur) - float(expected_dur or 0.0))
                        current_main_cursor_sec = max(0.0, float(seg_end or expected_dur or 0.0) - 0.12)
                        main_asset_ids.add(int(library_pick.id))
                        aid = int(library_pick.id)
                        asset_scene_use_count[aid] = int(asset_scene_use_count.get(aid, 0) or 0) + 1
                        current_main_consecutive = 1
                    else:
                        aid = int(library_pick.id)
                        asset_scene_use_count[aid] = int(asset_scene_use_count.get(aid, 0) or 0) + 1
                        current_main_consecutive = 0
                    if last_library_asset_id == aid:
                        consecutive_library_reuse += 1
                    else:
                        last_library_asset_id = aid
                        consecutive_library_reuse = 1
                    filled += 1
                    prev_scene_meta_for_rank = scene_meta
                    _upd(progress=min(95, 2 + int(i / total * 90)), message=(f"已绑定长视频主素材 {filled}/{total}：镜头 {scene_idx}" if library_role == "main" else f"已复用素材库 {filled}/{total}：镜头 {scene_idx}"))
                    continue
                except Exception:
                    library_pick = None
            if not web_items and not library_pick:
                retry_result = retry_scene_candidates(candidates=candidates, query=q, prefer=prefer, expected_dur=float(expected_dur or 0.0), scene_meta=scene_meta, narration=narration, project_title=project_title, pack_key=str(track_key), llm_cfg=llm_cfg, llm_cache=llm_cache, scene_deadline=scene_deadline, media_total_deadline=media_total_deadline, now_time=time.time, clean_query=_clean_query, search_images_only=_search_images_only, search_all=_search_all, rank_items=_rank_items, rewrite_to_en_keywords=_rewrite_to_en_keywords, llm_extra_queries=llm_extra_queries)
                if retry_result.web_items:
                    web_items = retry_result.web_items
                    query_used = retry_result.query_used or query_used
                    if retry_result.query_used and retry_result.query_used != q:
                        try:
                            with session_scope() as session:
                                sc2 = session.exec(select(Scene).where(Scene.id == int(scene_id))).first()
                                if sc2:
                                    cur = {}
                                    try:
                                        cur = json.loads(getattr(sc2, "meta_json", "{}") or "{}")
                                    except Exception:
                                        cur = {}
                                    s2 = dict(cur) if isinstance(cur, dict) else {}
                                    s2.setdefault("search", {})
                                    if isinstance(s2.get("search"), dict):
                                        s2["search"]["en_rewrite"] = retry_result.query_used
                                    sc2.meta_json = json.dumps(s2, ensure_ascii=True)
                                    sc2.updated_at = now_utc()
                                    session.add(sc2)
                        except Exception:
                            pass
                if retry_result.last_search_err is not None:
                    last_search_err = retry_result.last_search_err
            if not web_items and not library_pick and prefer == "video":
                image_fallback_queries: list[str] = []
                for fallback_query in [query_used, q, *candidates]:
                    normalized_query = str(fallback_query or "").strip()
                    if normalized_query and normalized_query not in image_fallback_queries:
                        image_fallback_queries.append(normalized_query)
                for one_q in image_fallback_queries[:5]:
                    if time.time() >= scene_deadline or time.time() >= media_total_deadline:
                        break
                    try:
                        image_items = _search_images_only(one_q)
                    except Exception as exc:
                        last_search_err = exc
                        continue
                    if not image_items:
                        continue
                    web_items = _rank_items(items=image_items, expected_dur=float(expected_dur or 0.0), query=one_q, scene_meta=scene_meta, prev_scene_meta=prev_scene_meta)
                    query_used = one_q
                    break
            if not web_items:
                if time.time() >= scene_deadline:
                    timed_out_scenes += 1
                    _record_failed_scene(scene_id=scene_id, scene_idx=scene_idx, reason_code="provider_timeout", reason_label="素材补齐超时", query_used=query_used or q, detail="素材搜索超时")
                    if len(errors) < 5:
                        errors.append(f"镜头 {scene_idx} 搜索超时")
                if last_search_err is not None:
                    search_errors += 1
                    code, label = classify_media_provider_error(str(last_search_err))
                    _record_failed_scene(scene_id=scene_id, scene_idx=scene_idx, reason_code=code, reason_label=label, query_used=query_used or q, detail=str(last_search_err))
                    if len(errors) < 5:
                        errors.append(f"镜头 {scene_idx} {label}")
                elif time.time() < scene_deadline:
                    _record_failed_scene(scene_id=scene_id, scene_idx=scene_idx, reason_code="no_results", reason_label="未找到可用素材", query_used=query_used or q, detail="未命中可用素材")
                if i % 2 == 0:
                    _upd(progress=min(95, 2 + int(i / total * 90)), message=f"未找到素材：镜头 {scene_idx}（{i}/{total}）")
                continue
            best_idx = -1
            best_conf = 0.0
            best_reason = ""
            if llm_cfg:
                best_idx, best_conf, best_reason = _llm_pick_best(narration=narration, query=query_used or q, items=web_items)
                if 0 <= best_idx < len(web_items):
                    try:
                        it0 = web_items.pop(int(best_idx))
                        web_items.insert(0, it0)
                    except Exception:
                        pass
            min_conf = 0.62
            needs_review = bool(scene_continuity_jump or (llm_cfg and best_conf and best_conf < min_conf))
            if needs_review and llm_cfg:
                try:
                    extra = llm_extra_queries(llm_cfg=llm_cfg, narration=narration, title=project_title, pack_key=str(track_key))
                except Exception:
                    extra = []
                for one_q in extra[:3]:
                    if one_q.strip() == (query_used or q).strip():
                        continue
                    try:
                        more_items = _search_all(one_q)
                    except Exception:
                        more_items = []
                    if not more_items:
                        continue
                    more_items = _rank_items(items=more_items, expected_dur=float(expected_dur or 0.0), query=one_q, scene_meta=scene_meta, prev_scene_meta=prev_scene_meta)
                    idx2, conf2, reason2 = _llm_pick_best(narration=narration, query=one_q, items=more_items)
                    if conf2 > best_conf and 0 <= idx2 < len(more_items):
                        best_conf = float(conf2)
                        best_reason = str(reason2 or best_reason)
                        query_used = one_q
                        try:
                            it0 = more_items.pop(int(idx2))
                            more_items.insert(0, it0)
                        except Exception:
                            pass
                        web_items = more_items
                        needs_review = bool(best_conf < min_conf)
                    if best_conf >= min_conf:
                        break
            if llm_cfg:
                try:
                    with session_scope() as session:
                        sc2 = session.exec(select(Scene).where(Scene.id == int(scene_id))).first()
                        if sc2:
                            cur = {}
                            try:
                                cur = json.loads(getattr(sc2, "meta_json", "{}") or "{}")
                            except Exception:
                                cur = {}
                            s2 = dict(cur) if isinstance(cur, dict) else {}
                            s2.setdefault("search", {})
                            if isinstance(s2.get("search"), dict):
                                s2["search"]["last_query"] = (query_used or q)[:120]
                                s2["search"]["best_confidence"] = float(best_conf or 0.0)
                                if best_reason:
                                    s2["search"]["llm_reason"] = best_reason
                                s2["search"].pop("needs_review", None)
                            sc2.meta_json = json.dumps(s2, ensure_ascii=True)
                            sc2.updated_at = now_utc()
                            session.add(sc2)
                except Exception:
                    pass
            import_result = import_candidate_assets(web_items=web_items or [], keep_running=keep_running, scene_deadline=scene_deadline, media_total_deadline=media_total_deadline, now_time=time.time, wait_if_job_paused=wait_if_job_paused, target_job_id=target_job_id, url_hash=url_hash, used_hashes=used_hashes, title_key=_title_key, used_title_keys=used_title_keys, recent_providers=recent_providers, import_to_project=import_to_project, import_request_cls=import_request_cls, project_id=int(project_id))
            a = import_result.asset
            picked_url = import_result.picked_url
            picked_provider = import_result.picked_provider
            last_import_err = import_result.last_import_err
            if last_import_err is not None and (not a or a.id is None):
                import_errors += 1
                _record_failed_scene(scene_id=scene_id, scene_idx=scene_idx, reason_code="import_failed", reason_label="素材导入失败", query_used=query_used or q, provider=str(picked_provider or "")[:40], detail=str(last_import_err))
                if len(errors) < 5:
                    errors.append(f"镜头 {scene_idx} 素材导入失败")
                continue
            if not a or a.id is None:
                if time.time() >= scene_deadline:
                    timed_out_scenes += 1
                    _record_failed_scene(scene_id=scene_id, scene_idx=scene_idx, reason_code="provider_timeout", reason_label="素材导入超时", query_used=query_used or q, detail="素材导入超时")
                    if len(errors) < 5:
                        errors.append(f"镜头 {scene_idx} 导入超时")
                continue
            apply_result = apply_imported_asset(asset=a, picked_url=picked_url, picked_provider=picked_provider, picked_main_candidate=picked_main_candidate, main_candidate_file_url=main_candidate_file_url, main_candidate_duration_sec=float(main_candidate_duration_sec or 0.0), expected_dur=float(expected_dur or 0.0), scene_idx=scene_idx, scene_id=scene_id, query_used=query_used, best_conf=float(best_conf or 0.0), best_reason=best_reason, set_scene_asset=_set_scene_asset, main_clip_window=_main_clip_window, asset_title_key=_asset_title_key, asset_duration_sec=_asset_duration_sec, url_hash=url_hash, used_hashes=used_hashes, used_title_keys=used_title_keys, recent_providers=recent_providers, used_asset_types=used_asset_types, used_providers=used_providers)
            meta_a = apply_result.meta_a
            selected_as_main = apply_result.selected_as_main
            aid = apply_result.aid
            last_library_asset_id = None
            consecutive_library_reuse = 0
            if selected_as_main:
                dur_main = float(main_candidate_duration_sec or 0.0)
                if dur_main <= 0:
                    dur_main = _asset_duration_sec(a, meta_a)
                current_main_asset_id = int(a.id)
                current_main_duration_sec = float(dur_main or 0.0)
                current_main_remaining_sec = max(0.0, dur_main - float(expected_dur or 0.0))
                main_seg = _main_clip_window(duration_sec=float(main_candidate_duration_sec or 0.0), expected_dur=float(expected_dur or 0.0), scene_idx=scene_idx)
                if main_seg[1] is not None:
                    current_main_cursor_sec = max(0.0, float(main_seg[1]) - 0.12)
                main_asset_ids.add(int(a.id))
                asset_scene_use_count[aid] = int(asset_scene_use_count.get(aid, 0) or 0) + 1
                current_main_consecutive = 1
            else:
                asset_scene_use_count[aid] = int(asset_scene_use_count.get(aid, 0) or 0) + 1
                current_main_consecutive = 0
            filled += 1
            prev_scene_meta_for_rank = scene_meta
            _upd(progress=min(95, 2 + int(i / total * 90)), message=(f"已绑定长视频主素材 {filled}/{total}：镜头 {scene_idx}" if selected_as_main else f"已填充 {filled}/{total}：镜头 {scene_idx}"))
        msg = f"自动填充完成：{filled}/{total}"
        if timed_out_scenes > 0:
            msg = f"{msg}；超时跳过 {timed_out_scenes} 个镜头"
        if failed_scene_reasons:
            patch_job_payload(target_job_id, {"media_failed_scenes": failed_scene_reasons[:20]})
        if provider_failure_events:
            patch_job_payload(target_job_id, {"media_provider_failures": provider_failure_events[:20]})
        if errors:
            msg = (msg + "；示例错误：" + "；".join(errors))[:900]
        if filled == 0 and active_providers == ["wikimedia"]:
            msg = (msg + "；提示：Wikimedia 可能被限流/拦截。可在设置->素材来源配置 Pexels/Pixabay API Key 提升成功率。")[:980]
        if filled == 0 and (search_errors > 0 or import_errors > 0):
            if keep_running:
                _upd(progress=100, message=msg)
            else:
                _upd(status="failed", progress=100, message=msg)
        else:
            _upd(status="done", progress=100, message=msg)
    except Exception as e:
        logger.exception("autofill_media failed job_id={} project_id={} error={}", job_id, project_id, sanitize_log_text(e))
        if keep_running:
            _upd(progress=100, message=f"自动填充失败：{e}")
        else:
            _upd(status="failed", progress=100, message=f"自动填充失败：{e}")
