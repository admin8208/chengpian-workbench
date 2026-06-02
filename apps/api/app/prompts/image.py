from app.scene_semantics import infer_scene_semantics, scene_negative_from_semantics, scene_prompt_from_semantics


def _cfg_bool(cfg: dict, key: str, default: bool) -> bool:
    value = cfg.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    low = str(value).strip().lower()
    if low in ("1", "true", "yes", "on"):
        return True
    if low in ("0", "false", "no", "off"):
        return False
    return default


def _clean_text(value) -> str:
    return str(value or "").strip()


def _frame_tokens(aspect: str) -> tuple[str, str]:
    if str(aspect or "").strip().lower() == "portrait":
        return ("vertical 9:16", "tall cinematic framing with safe top and bottom margins")
    return ("horizontal 16:9", "wide cinematic framing with safe side margins")


def build_image_prompts(pack, scene, *, with_quality_booster: bool = False, with_character_lock: bool = False, aspect: str = "landscape") -> tuple[str, str]:
    cfg = pack.config() if hasattr(pack, "config") else (pack if isinstance(pack, dict) else {})
    style = str(cfg.get("style", "cinematic composition")).strip() or "cinematic composition"
    pack_negative = str(cfg.get("negative", "")).strip()
    scene_prompt = str(getattr(scene, "image_prompt", "") or "").strip()
    scene_negative = str(getattr(scene, "image_negative", "") or "").strip()
    meta = {}
    try:
        import json

        meta = json.loads(str(getattr(scene, "meta_json", "{}") or "{}"))
        if not isinstance(meta, dict):
            meta = {}
    except Exception:
        meta = {}
    visual = meta.get("visual") if isinstance(meta.get("visual"), dict) else {}
    continuity = meta.get("continuity") if isinstance(meta.get("continuity"), dict) else {}
    narration = str(getattr(scene, "narration", "") or "").strip()
    sem = infer_scene_semantics(narration=narration, pack_key=str(getattr(pack, "key", "") or cfg.get("key", "")), visual_hint=visual)
    text_policy = sem.get("text_policy") if isinstance(sem.get("text_policy"), dict) else {}

    with_quality_booster = bool(with_quality_booster or _cfg_bool(cfg, "image_quality_booster", False))
    cinematic_realism = _cfg_bool(cfg, "image_cinematic_realism", True)

    # 中国审美和真实感基础提示词
    positive_parts = []
    pack_key = str(getattr(pack, "key", "") or cfg.get("key", "")).strip().lower()
    if pack_key == "history":
        positive_parts.extend(["Chinese historical aesthetic", "period-authentic environment"])
    else:
        positive_parts.extend(["Chinese people, Asian features", "modern Chinese environment"])
    if with_quality_booster:
        positive_parts.extend([
            "masterpiece",
            "best quality",
            "high detail",
            "photorealistic skin texture",
            "realistic facial anatomy",
            "natural hand structure",
            "clean material texture",
            "cinematic color separation",
        ])
    if with_character_lock:
        positive_parts.extend(["consistent character design", "same person as reference image"])
    anchor_subject = str(sem.get("anchor_subject") or visual.get("canonical_subject") or visual.get("anchor_subject") or visual.get("subject") or "").strip()
    anchor_setting = str(sem.get("anchor_setting") or visual.get("canonical_setting") or visual.get("anchor_setting") or visual.get("setting") or "").strip()
    continuity_mode = str(sem.get("continuity_mode") or visual.get("continuity_mode") or "").strip()
    camera_angle = str(sem.get("camera_angle") or visual.get("camera_angle") or "").strip()
    if anchor_subject:
        positive_parts.append(f"same subject: {anchor_subject}")
    if anchor_setting:
        positive_parts.append(f"same setting: {anchor_setting}")
    if str(visual.get("subject_entity_key") or "").strip():
        positive_parts.append("keep the same subject appearance, clothing and age when this is the same entity across shots")
    if str(visual.get("setting_entity_key") or "").strip():
        positive_parts.append("keep the same location layout and background identity when this is the same place across shots")
    if continuity_mode:
        positive_parts.append(f"continuity mode {continuity_mode}")
    if camera_angle:
        positive_parts.append(camera_angle)
    if bool(continuity.get("should_match_prev_subject")) or bool(continuity.get("should_match_prev_setting")):
        positive_parts.append("preserve scene continuity with previous shot")

    composition = _clean_text(visual.get("composition") or sem.get("shot"))
    lighting = _clean_text(visual.get("lighting") or sem.get("time"))
    lens_feel = _clean_text(visual.get("lens_feel") or visual.get("camera_movement") or sem.get("camera_intent"))
    color_mood = _clean_text(visual.get("color_mood") or visual.get("grade") or sem.get("emotion_state"))
    subject_size = _clean_text(visual.get("subject_size"))
    motion_intent = _clean_text(visual.get("motion_intent") or sem.get("transition_motivation"))
    canonical_wardrobe = _clean_text(visual.get("canonical_wardrobe") or visual.get("wardrobe"))
    canonical_props = visual.get("canonical_props") if isinstance(visual.get("canonical_props"), list) else []
    prop_text = ", ".join([_clean_text(x) for x in canonical_props if _clean_text(x)])
    scene_specific_prompt = scene_prompt

    if cinematic_realism:
        positive_parts.extend([
            "cinematic realism",
            "grounded real-world detail",
            "credible human emotion",
            "natural depth layering",
        ])
    if composition:
        positive_parts.append(f"composition: {composition}")
    if lighting:
        positive_parts.append(f"lighting: {lighting}")
    if lens_feel:
        positive_parts.append(f"lens feel: {lens_feel}")
    if color_mood:
        positive_parts.append(f"color mood: {color_mood}")
    if subject_size:
        positive_parts.append(f"subject size: {subject_size}")
    if motion_intent:
        positive_parts.append(f"shot progression: {motion_intent}")
    if canonical_wardrobe:
        positive_parts.append(f"keep wardrobe consistent: {canonical_wardrobe}")
    if prop_text:
        positive_parts.append(f"keep recurring props consistent: {prop_text}")
    if scene_specific_prompt:
        positive_parts.append(f"scene-specific direction: {scene_specific_prompt}")

    semantic_prompt = scene_prompt_from_semantics(
        idx=int(getattr(scene, "idx", 0) or 0),
        style=style,
        narration=narration,
        semantics=sem,
        aspect=aspect,
    )
    text_mode = str(text_policy.get("mode") or "forbid").strip().lower()
    if text_mode == "overlay":
        placement = str(text_policy.get("placement") or "top").strip().lower() or "top"
        positive_parts.append(f"reserve clean visual space at the {placement} for later overlay text")
    elif text_mode == "incidental":
        positive_parts.append("any scene text must stay small, natural, and not readable as the main focus")
    elif text_mode == "in_scene_required":
        positive_parts.append("scene text should appear only where naturally attached to object surfaces")
    frame_ratio, frame_guidance = _frame_tokens(aspect)
    positive_parts.extend([semantic_prompt, frame_ratio, frame_guidance])
    positive = ", ".join([p for p in positive_parts if p]).strip(" ,")

    # 负面提示词：排除不真实风格
    default_negatives = [
        "cartoon",
        "anime",
        "illustration",
        "painting",
        "drawing",
        "sketch",
        "western features",
        "foreign setting",
        "unrealistic",
        "distorted",
        "deformed",
        "bad hands",
        "extra fingers",
        "extra limbs",
        "broken anatomy",
        "mutated face",
        "blurry face",
        "low detail skin",
        "generic mood shot",
        "empty symbolic composition",
    ]
    sem_negative = scene_negative_from_semantics(sem)
    negatives = default_negatives + [pack_negative, scene_negative, sem_negative]
    negative = ", ".join([p for p in negatives if p]).strip(" ,")
    return positive, negative
