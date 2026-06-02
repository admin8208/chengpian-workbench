import re

from app.prompts.policies import PROMPT_META_VERSION
from app.storyboard_continuity import continuity_metrics_from_rows, scene_anchor_from_visual
from app.scene_semantics import default_scene_style, infer_scene_semantics, scene_prompt_from_semantics


_SCRIPT_CLICHE_OPENING_RE = re.compile(
    r"^(?:哈喽|hello|hi)?大家好|^今天(?:想)?(?:跟|和)?大家聊聊|^今天我们来聊聊|^今天来聊聊|^这(?:一|一整)?期(?:视频|内容)|^本期(?:视频|内容)|^接下来(?:带|给)?大家(?:看|讲|说|聊聊?)",
    re.IGNORECASE,
)


def _looks_like_cliche_opening(text: str) -> bool:
    head = str(text or "").strip()[:40]
    if not head:
        return False
    return bool(_SCRIPT_CLICHE_OPENING_RE.search(head))


def continuity_policy(pack_key: str) -> dict:
    key = str(pack_key or "").strip().lower()
    if key in ("emotion", "family_cn"):
        return {
            "match_prev_subject": True,
            "match_prev_setting": True,
            "hard_shift_allowed": False,
            "main_clip_bias": "strong",
        }
    if key == "history":
        return {
            "match_prev_subject": True,
            "match_prev_setting": False,
            "hard_shift_allowed": False,
            "main_clip_bias": "medium",
        }
    if key == "career":
        return {
            "match_prev_subject": True,
            "match_prev_setting": False,
            "hard_shift_allowed": False,
            "main_clip_bias": "medium",
        }
    return {
        "match_prev_subject": True,
        "match_prev_setting": False,
        "hard_shift_allowed": False,
        "main_clip_bias": "medium",
    }


def _entity_norm(text: str) -> str:
    raw = str(text or "").strip().lower()
    if not raw:
        return ""
    raw = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", raw)
    parts = [p for p in re.split(r"\s+", raw) if p]
    if not parts:
        return ""
    generic = {
        "person", "people", "man", "woman", "team", "group", "figure", "character",
        "人物", "人", "女人", "男人", "百姓", "士兵", "众人", "队伍",
        "place", "scene", "street", "room", "office", "city", "building",
        "地方", "场景", "街道", "房间", "办公室", "城市", "建筑",
        "object", "item", "thing", "东西", "物件", "物品",
    }
    kept = [p for p in parts if p not in generic]
    vals = kept or parts
    return " ".join(vals[:4]).strip()


def _entity_tokens(text: str) -> set[str]:
    norm = _entity_norm(text)
    if not norm:
        return set()
    return {p for p in re.split(r"\s+", norm) if p}


def _is_same_entity(text_a: str, text_b: str) -> bool:
    ta = _entity_tokens(text_a)
    tb = _entity_tokens(text_b)
    if not ta or not tb:
        return False
    if ta == tb:
        return True
    inter = ta & tb
    if inter and (len(inter) >= min(len(ta), len(tb)) or len(inter) >= 2):
        return True
    joined_a = " ".join(sorted(ta))
    joined_b = " ".join(sorted(tb))
    return joined_a in joined_b or joined_b in joined_a


def _prefer_entity_desc(current: str, candidate: str) -> str:
    cur = str(current or "").strip()
    cand = str(candidate or "").strip()
    if not cur:
        return cand
    if not cand:
        return cur
    return cand if len(cand) > len(cur) else cur


def _entity_key(kind: str, text: str, idx: int) -> str:
    norm = _entity_norm(text)
    base = re.sub(r"\s+", "_", norm).strip("_") or f"scene_{int(idx)}"
    return f"{kind}:{base}"[:80]


def default_search_en_from_query(text: str, track_query_bias) -> str:
    base = re.sub(r"[^A-Za-z0-9\s]", " ", str(text or "")).strip()
    base = re.sub(r"\s{2,}", " ", base)[:60]
    if re.search(r"[A-Za-z]", base) and not re.search(r"[\u4e00-\u9fff]", base):
        return base[:60]
    for x in track_query_bias:
        if x:
            return x
    return "lifestyle scene"


def search_en_from_visual_intent(visual: dict | None, track_query_bias: list[str]) -> str:
    vi = visual if isinstance(visual, dict) else {}
    parts = [str(vi.get("anchor_subject") or vi.get("subject") or "").strip(), str(vi.get("action") or "").strip(), str(vi.get("anchor_setting") or vi.get("setting") or "").strip(), str(vi.get("time") or "").strip()]
    return default_search_en_from_query(" ".join([p for p in parts if p]), track_query_bias)


def _default_lighting(*, pack_key: str, time_value: str, emotion_state: str, transition_hint: str) -> str:
    low_time = str(time_value or "").strip().lower()
    low_emotion = str(emotion_state or "").strip().lower()
    low_pack = str(pack_key or "").strip().lower()
    low_transition = str(transition_hint or "").strip().lower()
    if "night" in low_time or "夜" in low_time:
        if low_pack in ("emotion", "family_cn"):
            return "soft low-key practical night light"
        if low_pack == "history":
            return "warm candle or torch motivated light"
        return "controlled practical night light"
    if "dusk" in low_time or "evening" in low_time or "傍晚" in low_time:
        return "soft golden-hour side light"
    if "morning" in low_time or "清晨" in low_time or "早晨" in low_time:
        return "soft morning side light"
    if low_transition == "contrast":
        return "clean directional contrast light"
    if any(token in low_emotion for token in ("紧张", "压抑", "tense", "anxious", "restrained")):
        return "soft window light with restrained contrast"
    return "natural motivated daylight"


def _default_composition(*, shot: str, text_policy: dict | None, transition_hint: str) -> str:
    low_shot = str(shot or "").strip().lower()
    policy = text_policy if isinstance(text_policy, dict) else {}
    mode = str(policy.get("mode") or "").strip().lower()
    placement = str(policy.get("placement") or "top").strip().lower() or "top"
    if "close" in low_shot:
        base = "tight close-up, subject slightly off-center"
    elif "wide" in low_shot or "establish" in low_shot:
        base = "wide establishing composition with readable foreground-background depth"
    elif "medium" in low_shot:
        base = "medium shot, subject on frame right"
    else:
        base = "balanced cinematic composition with a clear main subject"
    if mode == "overlay":
        return f"{base}, leave clean {placement} negative space for later subtitle overlay"
    if str(transition_hint or "").strip().lower() == "contrast":
        return f"{base}, stronger visual separation between subject and background"
    return base


def _default_motion_intent(*, continuity_mode: str, transition_hint: str, shot: str) -> str:
    low_mode = str(continuity_mode or "").strip().lower()
    low_hint = str(transition_hint or "").strip().lower()
    low_shot = str(shot or "").strip().lower()
    if low_mode == "push_in":
        return "slow push in"
    if low_mode == "pull_out":
        return "gentle pull out"
    if low_mode == "same_place_new_angle":
        return "subtle pan left"
    if low_mode == "cutaway":
        return "hold still"
    if low_mode == "hard_shift" or low_hint == "cut":
        return "hold still"
    if low_hint == "contrast":
        return "gentle pull out"
    if "wide" in low_shot:
        return "subtle pan right"
    return "slow push in"


def enrich_storyboard_continuity(scenes: list[dict]) -> list[dict]:
    ordered = [dict(s or {}) for s in sorted(list(scenes or []), key=lambda x: int((x or {}).get("idx", 0) or 0))]
    pack_key = ""
    rows: list[dict] = []
    for it in ordered:
        meta = it.get("meta") if isinstance(it.get("meta"), dict) else {}
        if not pack_key:
            intent = meta.get("intent") if isinstance(meta.get("intent"), dict) else {}
            pack_key = str(intent.get("pack_key") or meta.get("pack_key") or "").strip().lower()
        visual = meta.get("visual") if isinstance(meta.get("visual"), dict) else {}
        rows.append({"idx": int(it.get("idx", 0) or 0), "narration": str(it.get("narration") or ""), "visual": visual})
    metrics = continuity_metrics_from_rows(rows)
    jumps = {int(b) for (_a, b) in list(metrics.get("jump_pairs") or [])}
    dom = str(metrics.get("dominant_anchor_id") or "")
    policy = continuity_policy(pack_key)
    n = max(1, len(ordered))
    subject_registry: dict[str, str] = {}
    setting_registry: dict[str, str] = {}
    prev_subject_key = ""
    prev_setting_key = ""
    out: list[dict] = []
    for i, it in enumerate(ordered):
        idx = int(it.get("idx", 0) or 0)
        row = dict(it)
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        visual = meta.get("visual") if isinstance(meta.get("visual"), dict) else {}
        story_meta = meta.get("story") if isinstance(meta.get("story"), dict) else {}
        search = meta.get("search") if isinstance(meta.get("search"), dict) else {}
        prompt_meta = meta.get("prompt") if isinstance(meta.get("prompt"), dict) else {}
        anc = scene_anchor_from_visual(visual, fallback_text=str(row.get("narration") or ""))
        role = "hook" if i == 0 else ("payoff" if i == n - 1 else ("reveal" if i >= int(n * 0.66) else "conflict"))
        continuity_mode = str(visual.get("continuity_mode") or "").strip().lower()
        transition_hint = str(story_meta.get("transition_hint") or "").strip().lower()
        raw_subject = str(visual.get("anchor_subject") or visual.get("subject") or "").strip()
        raw_setting = str(visual.get("anchor_setting") or visual.get("setting") or "").strip()

        subject_key = ""
        if raw_subject:
            for key, val in subject_registry.items():
                if _is_same_entity(raw_subject, val):
                    subject_key = key
                    subject_registry[key] = _prefer_entity_desc(val, raw_subject)
                    break
            if not subject_key:
                if continuity_mode in ("hold", "same_subject_new_action", "push_in", "pull_out") and prev_subject_key:
                    subject_key = prev_subject_key
                    subject_registry[subject_key] = _prefer_entity_desc(subject_registry.get(subject_key, ""), raw_subject)
                else:
                    subject_key = _entity_key("subject", raw_subject, idx)
                    subject_registry[subject_key] = raw_subject

        setting_key = ""
        if raw_setting:
            for key, val in setting_registry.items():
                if _is_same_entity(raw_setting, val):
                    setting_key = key
                    setting_registry[key] = _prefer_entity_desc(val, raw_setting)
                    break
            if not setting_key:
                if continuity_mode in ("hold", "same_place_new_angle", "push_in", "pull_out") and prev_setting_key:
                    setting_key = prev_setting_key
                    setting_registry[setting_key] = _prefer_entity_desc(setting_registry.get(setting_key, ""), raw_setting)
                else:
                    setting_key = _entity_key("setting", raw_setting, idx)
                    setting_registry[setting_key] = raw_setting

        canonical_subject = str(subject_registry.get(subject_key, raw_subject) or raw_subject).strip()
        canonical_setting = str(setting_registry.get(setting_key, raw_setting) or raw_setting).strip()
        visual2 = {
            **visual,
            "subject_entity_key": subject_key,
            "setting_entity_key": setting_key,
            "canonical_subject": canonical_subject,
            "canonical_setting": canonical_setting,
            "anchor_subject": canonical_subject or raw_subject,
            "anchor_setting": canonical_setting or raw_setting,
            "continuity_role": role,
            "continuity_mode": continuity_mode or "same_subject_new_action",
            "camera_angle": str(visual.get("camera_angle") or "").strip(),
            "lighting": str(visual.get("lighting") or "").strip(),
            "composition": str(visual.get("composition") or "").strip(),
            "motion_intent": str(visual.get("motion_intent") or "").strip(),
            "transition_motivation": str(visual.get("transition_motivation") or "").strip(),
        }
        anc = scene_anchor_from_visual(visual2, fallback_text=str(row.get("narration") or ""))
        visual2["anchor_id"] = str(anc.get("anchor_id") or "")
        visual2["anchor_type"] = str(anc.get("anchor_type") or "person")
        continuity = {
            "anchor_id": str(anc.get("anchor_id") or ""),
            "dominant_anchor_id": dom,
            "jump_from_prev": bool(idx in jumps),
            "anchor_coverage": float(metrics.get("anchor_coverage") or 0.0),
            "adjacent_jump_rate": float(metrics.get("adjacent_jump_rate") or 0.0),
            "should_match_prev_subject": bool(i > 0 and policy.get("match_prev_subject", True) and continuity_mode not in ("cutaway", "hard_shift") and subject_key and subject_key == prev_subject_key),
            "should_match_prev_setting": bool(i > 0 and policy.get("match_prev_setting", False) and continuity_mode not in ("cutaway", "hard_shift") and setting_key and setting_key == prev_setting_key),
            "allowed_hard_shift": bool(continuity_mode == "hard_shift" or transition_hint == "contrast" or policy.get("hard_shift_allowed", False)),
            "main_clip_bias": str(policy.get("main_clip_bias") or "medium"),
        }
        row["meta"] = {**meta, "visual": visual2, "search": search, "continuity": continuity, "prompt": {**prompt_meta, "version": PROMPT_META_VERSION}}
        out.append(row)
        prev_subject_key = subject_key or prev_subject_key
        prev_setting_key = setting_key or prev_setting_key
    return out


def humanize_scene_durations(durations: list[float], *, total_duration: float) -> list[float]:
    vals = [max(2.0, float(x or 2.0)) for x in durations]
    if not vals:
        return vals
    n = len(vals)
    shaped: list[float] = []
    for i, d in enumerate(vals):
        factor = 1.0
        if i == 0:
            factor *= 0.82
        elif i == 1:
            factor *= 0.92
        elif i == n - 1:
            factor *= 1.24
        elif i == n - 2:
            factor *= 1.08
        elif i % 3 == 0:
            factor *= 1.06
        elif i % 2 == 0:
            factor *= 0.96
        shaped.append(max(2.0, d * factor))
    s1 = float(sum(shaped))
    if s1 > 0 and total_duration > 0:
        scale = float(total_duration) / s1
        shaped = [max(2.0, x * scale) for x in shaped]
    delta = float(total_duration) - float(sum(shaped))
    if shaped:
        shaped[-1] = max(2.0, shaped[-1] + delta)
    return shaped


def canonical_script_from_scenes(scenes: list[dict]) -> str:
    ordered = sorted(
        [dict(s or {}) for s in list(scenes or []) if isinstance(s, dict)],
        key=lambda x: int(x.get("idx", 0) or 0),
    )
    lines = [str(row.get("narration", "") or "").strip() for row in ordered]
    return "\n".join([line for line in lines if line])


def normalize_storyboard_scene_durations(scenes: list[dict], *, target_sec: float) -> list[dict]:
    if not scenes:
        return scenes
    tgt = float(target_sec or 0.0)
    if tgt <= 0:
        return scenes
    durs = [max(2.0, float((s or {}).get("duration_sec", 0.0) or 2.0)) for s in scenes]
    shaped = humanize_scene_durations(durs, total_duration=tgt)
    out: list[dict] = []
    for i, s in enumerate(scenes):
        row = dict(s or {})
        row["duration_sec"] = max(2.0, float(shaped[i] if i < len(shaped) else durs[i]))
        out.append(row)
    return out


def normalize_storyboard_output(*, obj: dict, pack_key: str, topic: str, base_dur: float, target_sec: float, de_ai_phrase, track_query_bias: list[str], writer_name: str, prompt_workflow: str, default_image_prompt: str, intent_meta: dict | None = None, material_mode: str = "network") -> tuple[str, list[dict]]:
    script = de_ai_phrase(str(obj.get("script", "")).strip())
    scenes = obj.get("scenes")
    if not script or not isinstance(scenes, list) or not scenes:
        raise ValueError("invalid storyboard JSON")
    cleaned: list[dict] = []
    mode = str(material_mode or "network").strip().lower() or "network"
    for s in scenes:
        if not isinstance(s, dict):
            continue
        idx = int(s.get("idx", 0) or 0)
        narration = de_ai_phrase(str(s.get("narration", "")).strip())
        media_query = str(s.get("media_query", "")).strip()
        image_prompt = str(s.get("image_prompt", "")).strip()
        duration_sec = float(s.get("duration_sec", base_dur) or base_dur)
        image_negative = str(s.get("image_negative", "")).strip()
        if idx <= 0 or not narration:
            continue
        raw_vi = s.get("visual_intent") if isinstance(s.get("visual_intent"), dict) else {}
        vi = infer_scene_semantics(narration=narration, pack_key=pack_key, visual_hint=raw_vi)
        if not media_query:
            media_query = str(vi.get("subject") or narration).strip()[:24]
        semantic_style = str(raw_vi.get("theme") or raw_vi.get("visual_theme") or default_scene_style(pack_key)).strip() or default_scene_style(pack_key)
        semantic_prompt = scene_prompt_from_semantics(idx=idx, style=semantic_style, narration=narration, semantics=vi)
        if mode == "ai":
            if image_prompt:
                image_prompt = f"{semantic_prompt}, style note: {image_prompt}"
            else:
                image_prompt = semantic_prompt
        search_en = str(s.get("search_en", "") or "").strip()
        if mode != "ai" and not (re.search(r"[A-Za-z]", search_en) and not re.search(r"[\u4e00-\u9fff]", search_en)):
            search_en = search_en_from_visual_intent(vi, track_query_bias)
        elif mode == "ai" and not search_en:
            search_en = search_en_from_visual_intent(vi, track_query_bias)
        continuity_mode = str(s.get("continuity_mode") or "").strip().lower()
        if continuity_mode not in ("hold", "same_subject_new_action", "same_place_new_angle", "push_in", "pull_out", "cutaway", "hard_shift"):
            continuity_mode = "same_subject_new_action"
        transition_hint = str(s.get("transition_hint", "") or "").strip().lower()
        if transition_hint not in ("continue", "contrast", "cut"):
            transition_hint = "contrast" if continuity_mode == "hard_shift" else "continue"
        camera_angle = str(vi.get("camera_angle") or s.get("camera_angle") or "").strip()
        transition_motivation = str(vi.get("transition_motivation") or s.get("transition_motivation") or "").strip()
        text_policy = vi.get("text_policy") if isinstance(vi.get("text_policy"), dict) else {}
        lighting = str(raw_vi.get("lighting") or vi.get("lighting") or "").strip() or _default_lighting(
            pack_key=pack_key,
            time_value=str(vi.get("time") or ""),
            emotion_state=str(vi.get("emotion_state") or ""),
            transition_hint=transition_hint,
        )
        composition = str(raw_vi.get("composition") or vi.get("composition") or "").strip() or _default_composition(
            shot=str(vi.get("shot") or ""),
            text_policy=text_policy,
            transition_hint=transition_hint,
        )
        motion_intent = str(raw_vi.get("motion_intent") or vi.get("motion_intent") or "").strip() or _default_motion_intent(
            continuity_mode=continuity_mode,
            transition_hint=transition_hint,
            shot=str(vi.get("shot") or ""),
        )
        meta = {
            "intent": {**(intent_meta or {}), "pack_key": str(pack_key or "").strip().lower()},
            "screen": {"text": str(s.get("on_screen_text", "") or "").strip()},
                "visual": {
                    **vi,
                    "text_policy": text_policy,
                    "camera_angle": camera_angle,
                    "lighting": lighting,
                    "composition": composition,
                    "motion_intent": motion_intent,
                    "continuity_mode": continuity_mode,
                    "transition_motivation": transition_motivation,
                    "theme": str(s.get("visual_theme", "") or "").strip(),
                },
            "search": {"en": search_en, "anchor_query_en": search_en_from_visual_intent(vi, track_query_bias), "material_mode": mode},
            "story": {
                "template_stage": "",
                "scene_group": int(s.get("scene_group", 0) or 0),
                "transition_hint": transition_hint,
            },
            "pack_key": str(pack_key or "").strip().lower(),
            "prompt": {"version": PROMPT_META_VERSION, "workflow": prompt_workflow, "writer": writer_name, "material_mode": mode},
        }
        cleaned.append({"idx": idx, "narration": narration, "media_query": media_query, "image_prompt": image_prompt, "image_negative": image_negative, "duration_sec": max(2.0, duration_sec), "meta": meta})
    cleaned.sort(key=lambda x: x["idx"])
    if not cleaned:
        raise ValueError("no valid scenes")
    total_scenes = max(1, len(cleaned))
    for row in cleaned:
        idx = int(row.get("idx", 0) or 0)
        stage = "hook" if idx <= 1 else ("build" if idx <= max(2, int(total_scenes * 0.35)) else ("payoff" if idx >= max(3, int(total_scenes * 0.8)) else "middle"))
        row_meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        story_meta = row_meta.get("story") if isinstance(row_meta.get("story"), dict) else {}
        story_meta = dict(story_meta)
        story_meta["template_stage"] = stage
        row_meta["story"] = story_meta
        row["meta"] = row_meta
    cleaned = normalize_storyboard_scene_durations(cleaned, target_sec=target_sec)
    cleaned = enrich_storyboard_continuity(cleaned)
    canonical_script = canonical_script_from_scenes(cleaned)
    if _looks_like_cliche_opening(script):
        script = de_ai_phrase(canonical_script)
    if not script:
        script = canonical_script
    return script or canonical_script, cleaned
