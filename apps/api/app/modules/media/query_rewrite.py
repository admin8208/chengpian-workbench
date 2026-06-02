
import re
import time

from app.db import session_scope
from app.llm_client import LlmChatMessage, ollama_chat_json, openai_compat_chat_json
from app.llm_service import get_api_key, get_default_provider


_EN_REWRITE_CACHE: dict[str, tuple[str, float]] = {}
_CACHE_TTL_S = 3600.0


_CN_TO_EN_HINTS: list[tuple[str, str]] = [
    ("夜晚", "night"),
    ("白天", "day"),
    ("清晨", "morning"),
    ("日出", "sunrise"),
    ("日落", "sunset"),
    ("黄昏", "sunset"),
    ("城市", "city"),
    ("天际线", "skyline"),
    ("街头", "street"),
    ("办公室", "office"),
    ("办公", "office"),
    ("加班", "overtime"),
    ("会议", "meeting"),
    ("地铁", "subway"),
    ("车站", "station"),
    ("机场", "airport"),
    ("公园", "park"),
    ("河流", "river"),
    ("海边", "beach"),
    ("海浪", "ocean"),
    ("山", "mountain"),
    ("森林", "forest"),
    ("雨", "rain"),
    ("雪", "snow"),
    ("咖啡店", "cafe"),
    ("餐厅", "restaurant"),
    ("室内", "indoor"),
    ("户外", "outdoor"),
    ("近景", "close up"),
    ("特写", "close up"),
    ("慢动作", "slow motion"),
    ("人群", "crowd"),
    ("一个人", "person"),
    ("女人", "woman"),
    ("女生", "woman"),
    ("男人", "man"),
    ("男生", "man"),
    ("小孩", "child"),
    ("孩子", "child"),
]


def _has_cjk(s: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", s or ""))


def _clean_query(q: str) -> str:
    t = (q or "").strip()
    if not t:
        return ""
    # Keep it compact for stock footage search.
    t = re.sub(r"[\t\r\n]+", " ", t)
    t = re.sub(r"[\(\)\[\]{}<>\\/\|]+", " ", t)
    t = re.sub(r"[,;，；。.!！?？:：'\"]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:120]


def _looks_english(q: str) -> bool:
    t = (q or "").strip()
    if not t:
        return False
    if _has_cjk(t):
        return False
    # "english-ish": contains letters and is mostly ascii.
    if not re.search(r"[A-Za-z]", t):
        return False
    try:
        t.encode("ascii")
        return True
    except Exception:
        # Allow a bit of non-ascii but still treat as english-ish.
        return True


def _llm_cfg_from_db() -> dict:
    with session_scope() as session:
        p = get_default_provider(session)
        if not p:
            return {}
        api_key = ""
        try:
            api_key = get_api_key(session, int(p.id or 0)) if p.type == "openai_compat" else ""
        except Exception:
            api_key = ""
        return {
            "type": str(p.type or ""),
            "base_url": str(p.base_url or ""),
            "model": str(p.default_model or ""),
            "api_key": str(api_key or ""),
        }


def _rule_based_rewrite_cn_to_en(q: str) -> str:
    """Very small offline hint-based rewrite.

    This is only used when no LLM is configured or LLM rewrite fails.
    It is intentionally conservative.
    """

    t = _clean_query(q)
    if not t or not _has_cjk(t):
        return ""
    words: list[str] = []
    for cn, en in _CN_TO_EN_HINTS:
        if cn and cn in t:
            for w in en.split():
                if w and w not in words:
                    words.append(w)
    # Keep any existing ASCII words/numbers in the query.
    for w in re.findall(r"[A-Za-z0-9]+", t):
        ww = w.lower()
        if ww and ww not in words:
            words.append(ww)
    if len(words) < 2:
        return ""
    out = " ".join(words[:6]).strip()
    return out if _looks_english(out) else ""


def rewrite_to_en_stock_keywords(q: str, *, llm_cfg: dict | None = None) -> str:
    """Best-effort: rewrite Chinese query to concise EN stock footage keywords.

    - Returns "" if it cannot produce a safe english keyword string.
    - Uses an in-memory cache to avoid repeated LLM calls.
    """

    qq = _clean_query(q)
    if not qq:
        return ""
    if _looks_english(qq):
        return qq
    if not _has_cjk(qq):
        # Non-CJK but also not english-ish: don't guess.
        return ""

    now = time.time()
    hit = _EN_REWRITE_CACHE.get(qq)
    if hit and (now - float(hit[1])) <= _CACHE_TTL_S:
        return str(hit[0] or "")

    cfg = llm_cfg or _llm_cfg_from_db()
    base_url = str(cfg.get("base_url") or "")
    model = str(cfg.get("model") or "")
    provider_type = str(cfg.get("type") or "")
    api_key = str(cfg.get("api_key") or "")
    if not base_url or not model:
        out2 = _rule_based_rewrite_cn_to_en(qq)
        _EN_REWRITE_CACHE[qq] = (out2, now)
        return out2

    try:
        sys = (
            "Rewrite input into concise ENGLISH stock-footage keywords. "
            "Return STRICT JSON only: {\"q\": \"...\"}. "
            "Rules: 2-6 words, concrete nouns/actions, no punctuation, no full sentences."
        )
        user = f"Input: {qq}\nReturn JSON."
        messages = [LlmChatMessage(role="system", content=sys), LlmChatMessage(role="user", content=user)]

        if provider_type == "ollama":
            obj = ollama_chat_json(base_url=base_url, model=model, messages=messages)
        elif provider_type == "openai_compat":
            if not api_key:
                _EN_REWRITE_CACHE[qq] = ("", now)
                return ""
            obj = openai_compat_chat_json(base_url=base_url, api_key=api_key, model=model, messages=messages)
        else:
            _EN_REWRITE_CACHE[qq] = ("", now)
            return ""

        out_q = _clean_query(str((obj or {}).get("q") or ""))
        if out_q and _looks_english(out_q):
            _EN_REWRITE_CACHE[qq] = (out_q, now)
            return out_q
    except Exception:
        pass

    out2 = _rule_based_rewrite_cn_to_en(qq)
    _EN_REWRITE_CACHE[qq] = (out2, now)
    return out2
