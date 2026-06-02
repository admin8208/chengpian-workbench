import re

from app.prompts.base import json_only_rules
from app.prompts.composer import build_messages
from app.prompts.schemas import repair_storyboard_schema
from app.storyboard_continuity import continuity_metrics_from_rows


def build_storyboard_repair_messages(*, pack, topic: str, intent_family: str, format_id: str, tone: str, template_id: str, template_type: str, beats: list[str], bad_list: list[dict], storyboard_obj: dict):
    return build_messages(
        system_parts=[
            "You are a strict Chinese Douyin script doctor. Fix ONLY the flagged scenes.",
            json_only_rules(),
            "You will receive the current storyboard and a list of scene idx + reasons.",
            "Rules:",
            "- Keep scenes count and idx unchanged.",
            "- Rewrite ONLY the flagged scenes; keep others as-is.",
            "- Every scene must be filmable/searchable.",
            "- narration should be short spoken Chinese, internet-native.",
            "- media_query must be short Chinese keywords (no long sentences).",
            "- search_en must be 2-6 English words, no punctuation, no CJK.",
            "- visual_intent must include subject/action/setting/time/shot/lighting/composition/motion_intent.",
            "- Keep continuity with coherent transitions; avoid abrupt adjacent jumps.",
            "- Avoid real company/person names and insults.",
            f"JSON schema: {repair_storyboard_schema()}",
        ],
        user_parts=[
            f"Channel: {pack.name} ({pack.key})",
            f"Topic: {topic}",
            f"Intent: {intent_family}",
            f"Format: {format_id}",
            f"Tone: {tone}",
            f"Template: {template_id} ({template_type})",
            f"Beats: {beats}",
            f"Bad scenes: {bad_list}",
            f"Storyboard: {storyboard_obj}",
            "Repair them into concrete, filmable short-video scenes only.",
            "Fix now. Return JSON only.",
        ],
    )


def is_bad_scene_text(text: str) -> bool:
    s = str(text or "").strip()
    if not s:
        return True
    bad_markers = ["围绕", "推进情节", "给一个具体", "具体细节或例子", "关键点：围绕"]
    return any(m in s for m in bad_markers)


def looks_ok_search_en(query: str) -> bool:
    s = str(query or "").strip()
    if not s:
        return False
    if len(s) > 80:
        return False
    if not re.search(r"[A-Za-z]", s):
        return False
    if re.search(r"[\u4e00-\u9fff]", s):
        return False
    if re.search(r"[,;:/\\|\[\]{}()\"'`~!@#$%^&*+=?<>]", s):
        return False
    return True


def looks_ok_visual_intent(visual_intent: dict) -> bool:
    if not isinstance(visual_intent, dict):
        return False
    for key in ("subject", "action", "setting", "time", "shot", "lighting", "composition", "motion_intent"):
        if not str(visual_intent.get(key, "") or "").strip():
            return False
    return True


def collect_bad_storyboard_scenes(scenes_arr: list[dict]) -> list[dict]:
    bad: list[dict] = []
    rows: list[dict] = []
    for it in scenes_arr:
        if not isinstance(it, dict):
            continue
        idx = int(it.get("idx", 0) or 0)
        narration = str(it.get("narration", "") or "").strip()
        media_query = str(it.get("media_query", "") or "").strip()
        search_en = str(it.get("search_en", "") or "").strip()
        visual_intent = it.get("visual_intent") if isinstance(it.get("visual_intent"), dict) else {}
        if idx <= 0:
            continue
        if is_bad_scene_text(narration):
            bad.append({"idx": idx, "reason": "narration empty or template"})
            continue
        if idx == 1 and len(narration) > 40:
            bad.append({"idx": idx, "reason": "hook too long"})
            continue
        if not media_query or len(media_query) > 80:
            bad.append({"idx": idx, "reason": "media_query invalid"})
            continue
        if not looks_ok_search_en(search_en):
            bad.append({"idx": idx, "reason": "search_en invalid"})
            continue
        if not looks_ok_visual_intent(visual_intent):
            bad.append({"idx": idx, "reason": "visual_intent incomplete"})
            continue
        rows.append({"idx": idx, "narration": narration, "visual": visual_intent})

    rows.sort(key=lambda x: int(x.get("idx", 0) or 0))
    if len(rows) >= 4:
        cm = continuity_metrics_from_rows(rows)
        jump_rate = float(cm.get("adjacent_jump_rate") or 0.0)
        if jump_rate > 0.28:
            for _a, b in list(cm.get("jump_pairs") or [])[: max(2, min(6, len(rows) // 2))]:
                bad.append({"idx": int(b), "reason": "continuity jump with previous scene"})
    return bad
