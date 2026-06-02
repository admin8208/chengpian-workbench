def rewrite_to_en_keywords(
    *,
    query: str,
    clean_query,
    looks_english,
    llm_cfg: dict | None,
    en_rewrite_cache: dict[str, str],
    common_chinese_keywords: dict[str, str],
) -> str:
    normalized = clean_query(query)
    if not normalized:
        return ""
    if looks_english(normalized):
        return normalized

    for chinese, english in common_chinese_keywords.items():
        if chinese in normalized:
            return english

    if not llm_cfg:
        return ""
    if normalized in en_rewrite_cache:
        return en_rewrite_cache[normalized]

    try:
        from app.llm_client import LlmChatMessage, ollama_chat_json, openai_compat_chat_json

        base_url = str(llm_cfg.get("base_url") or "")
        model = str(llm_cfg.get("model") or "")
        api_key = str(llm_cfg.get("api_key") or "")
        provider_type = str(llm_cfg.get("type") or "")
        if not base_url or not model:
            return ""

        sys = (
            "Rewrite input into concise ENGLISH stock-footage keywords. "
            'Return STRICT JSON only: {"q": "..."}. '
            "Rules: 2-6 words, concrete nouns/actions, no punctuation, no full sentences. "
            "Use specific and descriptive terms that will yield high-quality stock footage. "
            "For example: 'happy family picnic', 'business meeting office', 'nature landscape mountains'"
        )
        user = f"Input: {normalized}\nReturn JSON."
        messages = [LlmChatMessage(role="system", content=sys), LlmChatMessage(role="user", content=user)]

        if provider_type == "ollama":
            obj = ollama_chat_json(base_url=base_url, model=model, messages=messages)
        elif provider_type == "openai_compat":
            if not api_key:
                return ""
            obj = openai_compat_chat_json(base_url=base_url, api_key=api_key, model=model, messages=messages)
        else:
            return ""
        out_q = clean_query(str((obj or {}).get("q") or ""))
        if out_q and looks_english(out_q):
            en_rewrite_cache[normalized] = out_q
            return out_q
    except Exception:
        pass

    en_rewrite_cache[normalized] = ""
    return ""


def generate_keyword_variants(keyword: str) -> list[str]:
    if not keyword:
        return []

    variants = [keyword]
    if keyword.endswith("s"):
        variants.append(keyword[:-1])
    else:
        variants.append(keyword + "s")

    synonyms = {
        "people": ["person", "individuals", "humans"],
        "city": ["urban", "town", "metropolis"],
        "nature": ["natural", "outdoor", "wild"],
        "technology": ["tech", "digital", "innovation"],
        "business": ["commerce", "corporate", "professional"],
    }

    for word, syns in synonyms.items():
        if word in keyword:
            for syn in syns:
                variants.append(keyword.replace(word, syn))

    return list(set(variants))[:3]
