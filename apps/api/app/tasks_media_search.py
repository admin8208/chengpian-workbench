import json
import math
import re
import time


def provider_available(*, provider: str, provider_blocked_until: dict[str, float]) -> bool:
    until = float(provider_blocked_until.get(str(provider or ""), 0.0) or 0.0)
    return time.time() >= until


def active_providers_for_query(*, active_providers: list[str], provider_blocked_until: dict[str, float]) -> list[str]:
    vals = [provider for provider in active_providers if provider_available(provider=provider, provider_blocked_until=provider_blocked_until)]
    return vals or list(active_providers)


def mark_provider_failure(*, provider: str, detail: str, provider_fail_counts: dict[str, int], provider_blocked_until: dict[str, float], classify_media_provider_error) -> None:
    key = str(provider or "").strip().lower()
    if not key:
        return
    count = int(provider_fail_counts.get(key, 0) or 0) + 1
    provider_fail_counts[key] = count
    err_code, _label = classify_media_provider_error(detail)
    cool_down = 0.0
    if err_code == "provider_502":
        cool_down = 90.0
    elif err_code in ("provider_timeout", "provider_network") and count >= 2:
        cool_down = 45.0
    if cool_down > 0:
        provider_blocked_until[key] = max(float(provider_blocked_until.get(key, 0.0) or 0.0), time.time() + cool_down)


def _pack_continuity_weights(pack_key: str) -> dict:
    key = str(pack_key or "").strip().lower()
    if key in ("emotion", "family_cn"):
        return {"subject": 0.9, "setting": 0.65, "style": 0.4, "jump_penalty": 0.7}
    if key in ("history", "career"):
        return {"subject": 0.6, "setting": 0.35, "style": 0.28, "jump_penalty": 0.45}
    return {"subject": 0.5, "setting": 0.3, "style": 0.2, "jump_penalty": 0.35}


def rank_items(*, items: list, expected_dur: float, query: str, scene_meta: dict | None, prev_scene_meta: dict | None, pack_key: str, tr: float, prefer: str, used_asset_types: list[str], used_providers: list[str], human_shot_bias) -> list:
    qlow = (query or "").strip().lower()
    toks = [token for token in re.split(r"\s+", qlow) if token][:6]
    continuity_weights = _pack_continuity_weights(pack_key)

    def aspect_score(width: int | None, height: int | None) -> float:
        if not width or not height or width <= 0 or height <= 0:
            return 0.0
        ratio = float(width) / float(height)
        dist = abs(math.log(max(1e-6, ratio / float(tr))))
        return max(0.0, 1.2 - dist * 1.4)

    def text_score(title: str) -> float:
        title_low = (title or "").lower()
        if not title_low or not toks:
            return 0.0
        hit = 0
        for token in toks:
            if token and token in title_low:
                hit += 1
        return float(hit) * 0.25

    def diversity_score(item) -> float:
        score = 0.0
        item_type = str(getattr(item, "kind", "") or "").lower()
        item_provider = str(getattr(item, "provider", "") or "").lower()
        if used_asset_types and item_type == used_asset_types[-1]:
            score -= 0.5
        if used_providers and item_provider == used_providers[-1]:
            score -= 0.3
        return score

    def score(item) -> float:
        score_value = 0.0
        provider = str(getattr(item, "provider", "") or "")
        kind = str(getattr(item, "kind", "") or "")
        title_low = str(getattr(item, "title", "") or "").lower()
        if provider == "pexels":
            score_value += 0.25
        elif provider == "pixabay":
            score_value += 0.15
        else:
            score_value += 0.05
        if str(pack_key or "").strip().lower() in ("emotion", "career", "family_cn"):
            if provider == "wikimedia":
                score_value -= 0.45
            elif provider == "pexels":
                score_value += 0.12

        if prefer == "video":
            score_value += 1.2 if kind == "video" else -0.55
        elif prefer == "image":
            score_value += 0.35 if kind == "image" else -0.1

        try:
            act = str(((scene_meta or {}).get("visual") or {}).get("action") or "").lower()
            shot = str(((scene_meta or {}).get("visual") or {}).get("shot") or "").lower()
            anc_sub = str(((scene_meta or {}).get("visual") or {}).get("anchor_subject") or ((scene_meta or {}).get("visual") or {}).get("subject") or "").lower()
            anc_set = str(((scene_meta or {}).get("visual") or {}).get("anchor_setting") or ((scene_meta or {}).get("visual") or {}).get("setting") or "").lower()
            continuity = ((scene_meta or {}).get("continuity") or {}) if isinstance((scene_meta or {}).get("continuity"), dict) else {}
            prev_visual = ((prev_scene_meta or {}).get("visual") or {}) if isinstance((prev_scene_meta or {}).get("visual"), dict) else {}
            prev_subject = str(prev_visual.get("anchor_subject") or prev_visual.get("subject") or "").lower()
            prev_setting = str(prev_visual.get("anchor_setting") or prev_visual.get("setting") or "").lower()
            prev_shot = str(prev_visual.get("shot") or "").lower()
            should_match_prev_subject = bool(continuity.get("should_match_prev_subject"))
            should_match_prev_setting = bool(continuity.get("should_match_prev_setting"))
            allowed_hard_shift = bool(continuity.get("allowed_hard_shift"))
        except Exception:
            act = ""
            shot = ""
            anc_sub = ""
            anc_set = ""
            prev_subject = ""
            prev_setting = ""
            prev_shot = ""
            should_match_prev_subject = False
            should_match_prev_setting = False
            allowed_hard_shift = False
        motion_need = bool(re.search(r"(walk|walking|run|running|leave|argue|talk|chat|hug|turn|look|waiting|gesture|commute|meeting|close up emotional)", act + " " + shot))
        if motion_need and kind == "video":
            score_value += 0.35
        if (not motion_need) and kind == "image":
            score_value += 0.04

        width = getattr(item, "width", None)
        height = getattr(item, "height", None)
        if width and height:
            resolution = width * height
            if resolution >= 1920 * 1080:
                score_value += 1.0
            elif resolution >= 1280 * 720:
                score_value += 0.7
            elif resolution >= 854 * 480:
                score_value += 0.4
            score_value += aspect_score(int(width), int(height))

        duration = getattr(item, "duration_sec", None)
        try:
            duration_value = float(duration) if duration is not None else 0.0
        except Exception:
            duration_value = 0.0
        if duration_value > 0 and expected_dur > 0:
            if duration_value >= expected_dur * 1.1:
                score_value += 1.0
            elif duration_value >= expected_dur * 0.75:
                score_value += 0.6
            else:
                score_value -= 0.28
        elif prefer == "video" and kind == "video":
            score_value -= 0.08

        score_value += text_score(str(getattr(item, "title", "") or ""))
        if anc_sub and any(token for token in re.split(r"\s+", anc_sub) if len(token) > 2 and token in title_low):
            score_value += 0.28
        if anc_set and any(token for token in re.split(r"\s+", anc_set) if len(token) > 2 and token in title_low):
            score_value += 0.18
        if prev_subject and any(token for token in re.split(r"\s+", prev_subject) if len(token) > 2 and token in title_low):
            score_value += continuity_weights["subject"]
        elif should_match_prev_subject and prev_subject and not allowed_hard_shift:
            score_value -= continuity_weights["jump_penalty"]
        if prev_setting and any(token for token in re.split(r"\s+", prev_setting) if len(token) > 2 and token in title_low):
            score_value += continuity_weights["setting"]
        elif should_match_prev_setting and prev_setting and not allowed_hard_shift:
            score_value -= continuity_weights["jump_penalty"] * 0.7
        if prev_shot and shot and prev_shot == shot:
            score_value += continuity_weights["style"] * 0.5
        if kind == "video" and should_match_prev_subject:
            score_value += continuity_weights["style"] * 0.3
        score_value += human_shot_bias(str(getattr(item, "title", "") or ""), query, provider)
        score_value += diversity_score(item)
        return score_value

    out = list(items or [])
    out.sort(key=score, reverse=True)
    return out


def llm_pick_best(*, llm_cfg: dict | None, narration: str, query: str, items: list) -> tuple[int, float, str]:
    if not llm_cfg:
        return (-1, 0.0, "")
    try:
        from app.llm_client import LlmChatMessage, ollama_chat_json, openai_compat_chat_json

        base_url = str(llm_cfg.get("base_url") or "")
        model = str(llm_cfg.get("model") or "")
        api_key = str(llm_cfg.get("api_key") or "")
        provider_type = str(llm_cfg.get("type") or "")
        if not base_url or not model:
            return (-1, 0.0, "")

        candidates = []
        for item in list(items or [])[:8]:
            candidates.append(
                {
                    "provider": str(getattr(item, "provider", "") or ""),
                    "kind": str(getattr(item, "kind", "") or ""),
                    "title": str(getattr(item, "title", "") or "")[:120],
                    "w": getattr(item, "width", None),
                    "h": getattr(item, "height", None),
                    "dur": getattr(item, "duration_sec", None),
                    "page": str(getattr(item, "page_url", "") or "")[:160],
                }
            )

        system = (
            "You are selecting the best stock media candidate for a short-video shot. "
            'Return STRICT JSON only: {"best_index": int, "confidence": number, "reason": string}. '
            "best_index is 0-based into the candidates list. Use -1 if none fit. "
            "confidence range 0..1. Prefer literal visual match to narration/query."
        )
        user = (
            f"Shot narration: {str(narration or '')[:220]}\n"
            f"Search query: {str(query or '')[:120]}\n"
            f"Candidates: {json.dumps(candidates, ensure_ascii=True)}\n"
            "Pick best candidate."
        )
        messages = [LlmChatMessage(role="system", content=system), LlmChatMessage(role="user", content=user)]

        if provider_type == "ollama":
            obj = ollama_chat_json(base_url=base_url, model=model, messages=messages)
        elif provider_type == "openai_compat":
            if not api_key:
                return (-1, 0.0, "")
            obj = openai_compat_chat_json(base_url=base_url, api_key=api_key, model=model, messages=messages)
        else:
            return (-1, 0.0, "")

        best_index = int((obj or {}).get("best_index", -1) or -1)
        try:
            confidence = float((obj or {}).get("confidence", 0.0) or 0.0)
        except Exception:
            confidence = 0.0
        reason = str((obj or {}).get("reason", "") or "")[:260]
        if best_index < -1:
            best_index = -1
        return (best_index, max(0.0, min(1.0, confidence)), reason)
    except Exception:
        return (-1, 0.0, "")


def search_all(*, query: str, prefer: str, active_providers: list[str], provider_blocked_until: dict[str, float], provider_keys: dict[str, str], media_total_deadline: float, search_timeout_s: int, target_aspect: str, search_web_media_parallel, search_web_media, mark_provider_failure_cb) -> list:
    all_items: list = []
    seen_urls: set[str] = set()
    providers_for_query = active_providers_for_query(active_providers=active_providers, provider_blocked_until=provider_blocked_until)
    try:
        if time.time() >= media_total_deadline:
            return []
        kinds = ["video", "image"] if prefer == "video" else ["image"]
        results = search_web_media_parallel(
            kinds=kinds,
            query=query,
            limit=5,
            provider_keys={provider: provider_keys.get(provider, "") for provider in providers_for_query},
            timeout_s=search_timeout_s,
            aspect=target_aspect,
            provider_failure_cb=mark_provider_failure_cb,
        ) or []
        for item in results:
            if hasattr(item, "file_url") and item.file_url:
                url = item.file_url
                if url not in seen_urls:
                    seen_urls.add(url)
                    all_items.append(item)
    except Exception:
        for provider in providers_for_query:
            key = provider_keys.get(provider, "")
            try:
                if time.time() >= media_total_deadline:
                    break
                if prefer == "video":
                    results = search_web_media(provider=provider, kind="video", query=query, limit=4, api_key=key, timeout_s=search_timeout_s, aspect=target_aspect) or []
                else:
                    results = search_web_media(provider=provider, kind="image", query=query, limit=3, api_key=key, timeout_s=search_timeout_s, aspect=target_aspect) or []
                for item in results:
                    if hasattr(item, "file_url") and item.file_url:
                        url = item.file_url
                        if url not in seen_urls:
                            seen_urls.add(url)
                            all_items.append(item)
            except Exception as exc:
                mark_provider_failure_cb(provider, str(exc))
                continue

    def score_item(item):
        score = 0.0
        if hasattr(item, "width") and hasattr(item, "height") and item.width and item.height:
            resolution = item.width * item.height
            if resolution >= 1920 * 1080:
                score += 10.0
            elif resolution >= 1280 * 720:
                score += 7.0
            elif resolution >= 854 * 480:
                score += 4.0
        if hasattr(item, "duration_sec") and item.duration_sec:
            if 5 <= item.duration_sec <= 60:
                score += 5.0
            elif 1 <= item.duration_sec < 5:
                score += 3.0
        if hasattr(item, "provider"):
            if item.provider == "pexels":
                score += 3.0
            elif item.provider == "pixabay":
                score += 2.0
        return score

    all_items.sort(key=score_item, reverse=True)
    return all_items[:10]


def search_images_only(*, query: str, active_providers: list[str], provider_blocked_until: dict[str, float], provider_keys: dict[str, str], media_total_deadline: float, search_timeout_s: int, target_aspect: str, search_web_media_parallel, search_web_media, mark_provider_failure_cb) -> list:
    all_items: list = []
    seen_urls: set[str] = set()
    providers_for_query = active_providers_for_query(active_providers=active_providers, provider_blocked_until=provider_blocked_until)
    try:
        if time.time() >= media_total_deadline:
            return []
        results = search_web_media_parallel(
            kinds=["image"],
            query=query,
            limit=5,
            provider_keys={provider: provider_keys.get(provider, "") for provider in providers_for_query},
            timeout_s=search_timeout_s,
            aspect=target_aspect,
            provider_failure_cb=mark_provider_failure_cb,
        ) or []
        for item in results:
            if hasattr(item, "file_url") and item.file_url:
                url = item.file_url
                if url not in seen_urls:
                    seen_urls.add(url)
                    all_items.append(item)
    except Exception:
        for provider in providers_for_query:
            key = provider_keys.get(provider, "")
            try:
                if time.time() >= media_total_deadline:
                    break
                results = search_web_media(provider=provider, kind="image", query=query, limit=3, api_key=key, timeout_s=search_timeout_s, aspect=target_aspect) or []
                for item in results:
                    if hasattr(item, "file_url") and item.file_url:
                        url = item.file_url
                        if url not in seen_urls:
                            seen_urls.add(url)
                            all_items.append(item)
            except Exception as exc:
                mark_provider_failure_cb(provider, str(exc))
                continue

    def score_item(item):
        score = 0.0
        if hasattr(item, "width") and hasattr(item, "height") and item.width and item.height:
            resolution = item.width * item.height
            if resolution >= 1920 * 1080:
                score += 10.0
            elif resolution >= 1280 * 720:
                score += 7.0
            elif resolution >= 854 * 480:
                score += 4.0
        if hasattr(item, "provider"):
            if item.provider == "pexels":
                score += 3.0
            elif item.provider == "pixabay":
                score += 2.0
        return score

    all_items.sort(key=score_item, reverse=True)
    return all_items[:8]
