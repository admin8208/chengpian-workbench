from dataclasses import dataclass
import re


@dataclass
class SceneCandidateSearchResult:
    query_used: str = ""
    web_items: list | None = None
    library_pick: object | None = None
    library_pick_meta: dict | None = None
    picked_main_candidate: bool = False
    main_candidate_file_url: str = ""
    main_candidate_duration_sec: float = 0.0
    last_search_err: Exception | None = None


@dataclass
class SceneRetrySearchResult:
    web_items: list | None = None
    query_used: str = ""
    last_search_err: Exception | None = None


def search_scene_candidates(
    *,
    candidates: list[str],
    prefer: str,
    want_new_main_clip: bool,
    remaining_expected_dur: float,
    expected_dur: float,
    scene_meta: dict,
    scene_deadline: float,
    media_total_deadline: float,
    now_time,
    search_all,
    search_images_only,
    rank_items,
    pick_main_web_item,
    search_library_assets,
    pick_main_library_hit,
) -> SceneCandidateSearchResult:
    result = SceneCandidateSearchResult(web_items=[] , library_pick_meta={})
    for one_q in candidates:
        if now_time() >= scene_deadline or now_time() >= media_total_deadline:
            break
        try:
            web_items = search_all(one_q)
            if web_items:
                web_items = rank_items(items=web_items, expected_dur=remaining_expected_dur, query=one_q, scene_meta=scene_meta)
                if want_new_main_clip:
                    main_item = pick_main_web_item(web_items, remaining_expected_dur)
                    if main_item is not None:
                        result.main_candidate_file_url = str(getattr(main_item, "file_url", "") or "").strip()
                        try:
                            result.main_candidate_duration_sec = float(getattr(main_item, "duration_sec", 0.0) or 0.0)
                        except Exception:
                            result.main_candidate_duration_sec = 0.0
                        web_items = [main_item, *[item for item in web_items if item is not main_item]]
                        result.picked_main_candidate = True
                result.web_items = web_items
                result.query_used = one_q
                break
        except Exception as exc:
            result.last_search_err = exc

        lib_hits = search_library_assets(one_q)
        if lib_hits:
            lib_choice = pick_main_library_hit(lib_hits, remaining_expected_dur) if want_new_main_clip else None
            if lib_choice is not None:
                result.library_pick, result.library_pick_meta, _lib_score = lib_choice
                result.picked_main_candidate = True
            else:
                result.library_pick, result.library_pick_meta, _lib_score = lib_hits[0]
            result.query_used = one_q
            break
    return result


def retry_scene_candidates(
    *,
    candidates: list[str],
    query: str,
    prefer: str,
    expected_dur: float,
    scene_meta: dict,
    narration: str,
    project_title: str,
    pack_key: str,
    llm_cfg: dict | None,
    llm_cache: dict[str, list[str]],
    scene_deadline: float,
    media_total_deadline: float,
    now_time,
    clean_query,
    search_images_only,
    search_all,
    rank_items,
    rewrite_to_en_keywords,
    llm_extra_queries,
) -> SceneRetrySearchResult:
    result = SceneRetrySearchResult(web_items=[])

    simple_candidates: list[str] = []
    for base_q in candidates[:2]:
        toks = [tok for tok in re.split(r"\s+", clean_query(base_q)) if tok]
        if toks:
            simple_candidates.append(toks[0])
        if len(toks) > 1:
            simple_candidates.append(" ".join(toks[:2]))
    for one_q in [q2 for q2 in simple_candidates if q2 and q2 not in candidates][:3]:
        if now_time() >= scene_deadline or now_time() >= media_total_deadline:
            break
        try:
            web_items = search_all(one_q)
            if web_items:
                result.web_items = rank_items(items=web_items, expected_dur=float(expected_dur or 0.0), query=one_q, scene_meta=scene_meta)
                result.query_used = one_q
                return result
        except Exception as exc:
            result.last_search_err = exc

    en_q = rewrite_to_en_keywords(query)
    if en_q:
        if now_time() >= scene_deadline or now_time() >= media_total_deadline:
            en_q = ""
    if en_q:
        try:
            web_items = search_all(en_q)
            if web_items:
                result.web_items = rank_items(items=web_items, expected_dur=float(expected_dur or 0.0), query=en_q, scene_meta=scene_meta)
                result.query_used = en_q
                return result
        except Exception as exc:
            result.last_search_err = exc

    if llm_cfg:
        if now_time() >= scene_deadline or now_time() >= media_total_deadline:
            extra = []
        else:
            cache_key = (project_title + "\n" + narration).strip()[:200]
            extra = llm_cache.get(cache_key)
            if extra is None:
                extra = llm_extra_queries(llm_cfg=llm_cfg, narration=narration, title=project_title, pack_key=pack_key)
                llm_cache[cache_key] = extra
        for one_q in extra:
            if now_time() >= scene_deadline or now_time() >= media_total_deadline:
                break
            try:
                web_items = search_all(one_q)
                if web_items:
                    result.web_items = rank_items(items=web_items, expected_dur=float(expected_dur or 0.0), query=one_q, scene_meta=scene_meta)
                    result.query_used = one_q
                    return result
            except Exception as exc:
                result.last_search_err = exc

    return result
