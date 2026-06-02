import re

from app.prompts import track_query_bias
from app.storyboard_postprocess import default_search_en_from_query, search_en_from_visual_intent


def clean_query(query: str) -> str:
    text = (query or "").strip()
    if not text:
        return ""

    bad_words = [
        "anime",
        "illustration",
        "cinematic",
        "composition",
        "masterpiece",
        "best quality",
        "high detail",
        "watermark",
        "text",
        "scene",
        "sdxl",
        "lora",
    ]
    normalized = text
    low = normalized.lower()
    for word in bad_words:
        if word in low:
            normalized = re.sub(re.escape(word), " ", normalized, flags=re.IGNORECASE)
            low = normalized.lower()

    normalized = re.sub(r"第\s*\d+\s*个(关键点|要点|部分)?", " ", normalized)
    normalized = re.sub(r"(关键点|要点|总结|结论)\s*[:：]", " ", normalized)
    normalized = re.sub(r"^(关于|聊聊|讲讲|说说)\s*", " ", normalized)
    normalized = re.sub(r"[\t\r\n]+", " ", normalized)
    normalized = re.sub(r"[\[\]（）(){}<>《》【】,，。.!！?？:：;；'\"`~|\\/]+", " ", normalized)
    normalized = re.sub(r"\s{2,}", " ", normalized).strip()
    return normalized[:60]


def looks_english(query: str) -> bool:
    text = (query or "").strip()
    if not text:
        return False
    has_lat = bool(re.search(r"[A-Za-z]", text))
    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", text))
    return has_lat and not has_cjk


def _continuity_priority_queries(*, scene_meta: dict, prev_scene_meta: dict | None, pack_key: str) -> list[str]:
    candidates: list[str] = []
    visual = scene_meta.get("visual") if isinstance(scene_meta.get("visual"), dict) else {}
    prev_meta = prev_scene_meta if isinstance(prev_scene_meta, dict) else {}
    prev_visual = prev_meta.get("visual") if isinstance(prev_meta.get("visual"), dict) else {}
    continuity = scene_meta.get("continuity") if isinstance(scene_meta.get("continuity"), dict) else {}
    should_match_prev_subject = bool(continuity.get("should_match_prev_subject"))
    should_match_prev_setting = bool(continuity.get("should_match_prev_setting"))
    prev_subject = str(prev_visual.get("anchor_subject") or prev_visual.get("subject") or "").strip()
    prev_setting = str(prev_visual.get("anchor_setting") or prev_visual.get("setting") or "").strip()
    cur_subject = str(visual.get("anchor_subject") or visual.get("subject") or "").strip()
    cur_action = str(visual.get("action") or "").strip()
    cur_setting = str(visual.get("anchor_setting") or visual.get("setting") or "").strip()
    cur_time = str(visual.get("time") or "").strip()

    if should_match_prev_subject and prev_subject:
        q = clean_query(" ".join([prev_subject, cur_action, prev_setting or cur_setting, cur_time]))
        if q and q not in candidates:
            candidates.append(q)
    if should_match_prev_setting and prev_setting:
        q = clean_query(" ".join([cur_subject or prev_subject, cur_action, prev_setting, cur_time]))
        if q and q not in candidates:
            candidates.append(q)
    if (str(pack_key or "").strip().lower() in ("emotion", "family_cn")) and prev_subject and prev_setting:
        q = clean_query(" ".join([prev_subject, prev_setting, cur_action]))
        if q and q not in candidates:
            candidates.append(q)
    return candidates


def build_query_candidates(*, media_query: str, narration: str, title: str, pack_key: str, scene_meta: dict | None = None, prev_scene_meta: dict | None = None) -> list[str]:
    candidates: list[str] = []

    meta = scene_meta if isinstance(scene_meta, dict) else {}
    visual = meta.get("visual") if isinstance(meta.get("visual"), dict) else {}
    prev_meta = prev_scene_meta if isinstance(prev_scene_meta, dict) else {}
    try:
        q_en = str((meta.get("search") or {}).get("en") or "").strip()
    except Exception:
        q_en = ""
    try:
        q_en2 = str((meta.get("search") or {}).get("en_rewrite") or "").strip()
    except Exception:
        q_en2 = ""
    try:
        q_anchor = str((meta.get("search") or {}).get("anchor_query_en") or "").strip()
    except Exception:
        q_anchor = ""
    if not q_anchor:
        try:
            visual2 = meta.get("visual") if isinstance(meta.get("visual"), dict) else {}
            anchor_subject = str(visual2.get("anchor_subject") or visual2.get("subject") or "").strip()
            anchor_setting = str(visual2.get("anchor_setting") or visual2.get("setting") or "").strip()
            q_anchor = clean_query(f"{anchor_subject} {anchor_setting}")
        except Exception:
            q_anchor = ""

    visual_q = search_en_from_visual_intent(visual, track_query_bias(pack_key)) if visual else ""
    shot_q = ""
    if visual:
        try:
            subject = str(visual.get("anchor_subject") or visual.get("subject") or "").strip()
            action = str(visual.get("action") or "").strip()
            setting = str(visual.get("anchor_setting") or visual.get("setting") or "").strip()
            shot = str(visual.get("shot") or "").strip()
            theme = str(visual.get("theme") or "").strip()
            shot_q = search_en_from_visual_intent(
                {
                    "subject": subject,
                    "action": action,
                    "setting": setting,
                    "time": str(visual.get("time") or "").strip(),
                },
                track_query_bias(pack_key),
            )
            extra_q = clean_query(" ".join([subject, action, setting, shot, theme]))
            if extra_q and extra_q not in candidates:
                candidates.append(extra_q)
        except Exception:
            shot_q = ""

    for item in _continuity_priority_queries(scene_meta=meta, prev_scene_meta=prev_meta, pack_key=pack_key):
        if item and item not in candidates:
            candidates.append(item)

    for item in [q_en, q_anchor, visual_q, shot_q, q_en2]:
        query_value = clean_query(item)
        if query_value and query_value not in candidates:
            candidates.append(query_value)

    if looks_english(media_query):
        query_value = clean_query(media_query)
        if query_value and query_value not in candidates:
            candidates.append(query_value)

    if not candidates:
        fallback = default_search_en_from_query(" ".join([media_query, narration, title]), track_query_bias(pack_key))
        query_value = clean_query(fallback)
        if query_value:
            candidates.append(query_value)

    return candidates[:4]


def llm_extra_queries(*, llm_cfg: dict, narration: str, title: str, pack_key: str) -> list[str]:
    try:
        from app.llm_client import LlmChatMessage, ollama_chat_json, openai_compat_chat_json

        base_url = str(llm_cfg.get("base_url") or "")
        model = str(llm_cfg.get("model") or "")
        api_key = str(llm_cfg.get("api_key") or "")
        provider_type = str(llm_cfg.get("type") or "")

        sys = (
            "You generate short search queries for stock footage/photo sites (Pexels/Pixabay/Wikimedia).\n"
            "Return STRICT JSON only.\n"
            'Schema: {"queries": [string, ...]}\n'
            "Rules:\n"
            "- Each query <= 6 words (English) or <= 12 Chinese characters.\n"
            "- Focus on visible people objects actions locations; avoid abstract words.\n"
            "- No punctuation, no emojis, no hashtags.\n"
        )
        user = (
            f"Title: {title}\n"
            f"Narration: {narration}\n"
            f"Track hints: {track_query_bias(pack_key)}\n"
            "Give 4 alternative queries (mix of Chinese and English is OK)."
        )
        messages = [LlmChatMessage(role="system", content=sys), LlmChatMessage(role="user", content=user)]

        if not base_url or not model:
            return []
        if provider_type == "ollama":
            obj = ollama_chat_json(base_url=base_url, model=model, messages=messages)
        elif provider_type == "openai_compat":
            if not api_key:
                return []
            obj = openai_compat_chat_json(base_url=base_url, api_key=api_key, model=model, messages=messages)
        else:
            return []

        queries = obj.get("queries")
        if not isinstance(queries, list):
            return []
        out: list[str] = []
        for query in queries:
            normalized = clean_query(str(query))
            if normalized and normalized not in out:
                out.append(normalized)
        return out[:6]
    except Exception:
        return []
