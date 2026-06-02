from __future__ import annotations

import re


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def _pack_defaults(pack_key: str) -> dict:
    key = str(pack_key or "").strip().lower()
    if key == "history":
        return {
            "subject": "历史人物或关键器物",
            "setting": "古代场景或历史空间",
            "time": "白天或烛光夜晚",
            "shot": "documentary medium close shot",
            "camera_intent": "medium close documentary framing",
            "emotion_state": "克制、紧张",
        }
    if key == "emotion":
        return {
            "subject": "关系中的人物",
            "setting": "家中或街头的真实生活场景",
            "time": "傍晚或夜晚",
            "shot": "close up emotional shot",
            "camera_intent": "close emotional framing",
            "emotion_state": "压抑、克制",
        }
    if key == "family_cn":
        return {
            "subject": "家庭成员",
            "setting": "客厅、饭桌或电话场景",
            "time": "傍晚暖光",
            "shot": "medium realistic shot",
            "camera_intent": "medium domestic framing",
            "emotion_state": "隐忍、别扭",
        }
    return {
        "subject": "职场人物",
        "setting": "办公室、会议室或通勤场景",
        "time": "工作日白天或夜晚",
        "shot": "medium handheld shot",
        "camera_intent": "medium natural framing",
        "emotion_state": "克制、专注",
    }


def default_scene_style(pack_key: str) -> str:
    key = str(pack_key or "").strip().lower()
    if key == "history":
        return "Chinese historical aesthetic"
    if key == "emotion":
        return "cinematic realism"
    if key == "family_cn":
        return "warm domestic realism"
    return "cinematic realism"


def _keyword_pick(text: str, mapping: list[tuple[list[str], str]], default: str) -> str:
    low = str(text or "").lower()
    for keys, value in mapping:
        if any(k in low for k in keys):
            return value
    return default


def _extract_key_objects(text: str) -> list[str]:
    obj_map = [
        (["手机", "消息", "微信", "屏幕", "通话"], "手机"),
        (["餐桌", "饭桌", "碗", "筷", "饭菜"], "餐桌和碗筷"),
        (["门", "门口", "门把手"], "门口"),
        (["电脑", "屏幕", "键盘", "文档"], "电脑与屏幕"),
        (["会议", "文件", "报告", "ppt"], "文件或汇报材料"),
        (["酒杯", "茶杯", "水杯"], "杯子"),
        (["照片", "相册"], "照片"),
        (["车", "地铁", "公交"], "交通工具"),
        (["圣旨", "玉玺", "奏折", "兵符", "卷轴"], "关键历史器物"),
    ]
    out: list[str] = []
    for keys, label in obj_map:
        if any(k in text for k in keys) and label not in out:
            out.append(label)
    return out[:4]


def _extract_subject(text: str, default: str) -> str:
    raw = str(text or "")
    subject_map = [
        (["她", "女生", "女人", "妻子", "母亲", "女儿"], "年轻女性"),
        (["他", "男人", "丈夫", "父亲", "儿子", "男生"], "成年男性"),
        (["他们", "两个人", "情侣", "夫妻"], "两个人物"),
        (["领导", "上司", "老板"], "领导角色"),
        (["同事", "员工", "实习生"], "职场人物"),
        (["皇帝", "大臣", "将军", "士兵"], "历史人物"),
        (["孩子", "小孩"], "孩子"),
    ]
    for keys, label in subject_map:
        if any(k in raw for k in keys):
            return label
    if re.search(r"[我你他她它们他们她们咱们我们]", raw):
        return default
    head = re.split(r"[，。！？：:；;]", raw)[0].strip()
    if 2 <= len(head) <= 14:
        return head
    return default


def _extract_action(text: str) -> str:
    raw = _clean_text(text)
    if not raw:
        return "处在一个具体瞬间"
    fragments = [seg.strip("，。！？；; ") for seg in re.split(r"[，。！？；;]", raw) if seg.strip()]
    if not fragments:
        return raw[:40]
    first = fragments[0]
    if len(first) > 34 and len(fragments) > 1:
        first = f"{first[:24]}，{fragments[1][:12]}"
    return first[:40]


def _extract_setting(text: str, default: str) -> str:
    setting_map = [
        (["厨房"], "家中厨房"),
        (["客厅", "沙发"], "家中客厅"),
        (["餐桌", "饭桌"], "饭桌旁"),
        (["卧室", "床边"], "卧室"),
        (["门口", "楼道", "走廊"], "门口或走廊"),
        (["办公室", "工位", "公司"], "办公室工位"),
        (["会议室", "开会"], "会议室"),
        (["电梯"], "电梯间"),
        (["地铁", "公交", "通勤"], "通勤场景"),
        (["街头", "路边", "巷子"], "街头"),
        (["宫殿", "大殿", "朝堂"], "古代宫殿"),
        (["营帐", "军营"], "古代军营"),
    ]
    return _keyword_pick(text, setting_map, default)


def _extract_time(text: str, default: str) -> str:
    time_map = [
        (["深夜", "夜里", "晚上", "夜晚"], "夜晚"),
        (["清晨", "早上", "晨"], "清晨"),
        (["傍晚", "黄昏"], "傍晚"),
        (["白天", "中午", "午后"], "白天"),
        (["烛光"], "烛光夜晚"),
    ]
    return _keyword_pick(text, time_map, default)


def _extract_emotion(text: str, default: str) -> str:
    emotion_map = [
        (["沉默", "没说话", "闭嘴"], "沉默、压抑"),
        (["犹豫", "没发出去", "停住", "忍住"], "犹豫、克制"),
        (["争吵", "吵", "对峙"], "紧张、对峙"),
        (["委屈", "难受"], "委屈、压抑"),
        (["生气", "愤怒"], "愤怒、克制"),
        (["紧张", "慌"], "紧张、僵住"),
    ]
    return _keyword_pick(text, emotion_map, default)


def infer_text_policy(*, narration: str, on_screen_text: str = "", visual_hint: dict | None = None) -> dict:
    text = _clean_text(narration)
    overlay_text = _clean_text(on_screen_text)
    hint = visual_hint if isinstance(visual_hint, dict) else {}
    raw_mode = str(hint.get("mode") or hint.get("text_mode") or "").strip().lower()
    if raw_mode in ("forbid", "incidental", "overlay", "in_scene_required"):
        mode = raw_mode
    elif overlay_text:
        mode = "overlay"
    elif any(token in text for token in ("手机消息", "短信", "微信消息", "聊天记录", "屏幕上那句话", "屏幕上的一句话", "那句话", "消息内容")):
        mode = "overlay"
    elif any(token in text for token in ("手机", "消息", "短信", "微信", "聊天记录", "屏幕", "界面", "白板", "文件", "卷轴", "奏折", "招牌", "牌匾", "海报", "标题")):
        if any(token in text for token in ("写着", "写了", "显示", "内容", "标题", "字幕", "一句话", "几个字")):
            mode = "overlay"
        else:
            mode = "incidental"
    else:
        mode = "forbid"

    if any(token in text for token in ("牌匾", "招牌", "卷轴", "奏折", "文件上", "纸上写着")) and not overlay_text:
        mode = "in_scene_required"

    placement = str(hint.get("placement") or "").strip().lower()
    if placement not in ("top", "center", "bottom", "object_bound", "auto"):
        if mode == "overlay":
            placement = "top"
        elif mode == "in_scene_required":
            placement = "object_bound"
        else:
            placement = "auto"

    readability = str(hint.get("readability") or "").strip().lower()
    if readability not in ("none", "low", "medium", "high"):
        readability = "none" if mode == "forbid" else ("low" if mode == "incidental" else "high")

    style = str(hint.get("style") or "").strip().lower()
    if style not in ("subtitle", "chat_ui", "signage", "document", "caption"):
        if any(token in text for token in ("手机", "消息", "短信", "微信", "聊天记录", "界面")):
            style = "chat_ui"
        elif any(token in text for token in ("牌匾", "招牌", "海报")):
            style = "signage"
        elif any(token in text for token in ("卷轴", "奏折", "文件", "白板", "纸上")):
            style = "document"
        else:
            style = "caption"

    content = overlay_text
    if not content and mode == "overlay":
        for m in re.findall(r"[“\"]([^”\"]{1,20})[”\"]", text):
            if m.strip():
                content = m.strip()
                break
    if not content and mode == "overlay" and any(token in text for token in ("消息", "短信", "聊天记录", "标题", "字幕")):
        content = "保留后期叠字空间"

    max_chars = 12 if style in ("subtitle", "caption", "chat_ui") else 8
    try:
        max_chars = int(hint.get("max_chars") or max_chars)
    except Exception:
        max_chars = max_chars
    max_chars = max(4, min(24, max_chars))

    return {
        "mode": mode,
        "content": content[: max_chars * 2].strip(),
        "placement": placement,
        "readability": readability,
        "style": style,
        "max_chars": max_chars,
    }


def infer_scene_semantics(*, narration: str, pack_key: str, visual_hint: dict | None = None) -> dict:
    defaults = _pack_defaults(pack_key)
    text = _clean_text(narration)
    hint = visual_hint if isinstance(visual_hint, dict) else {}
    subject = str(hint.get("subject") or "").strip() or _extract_subject(text, defaults["subject"])
    action = str(hint.get("action") or "").strip() or _extract_action(text)
    setting = str(hint.get("setting") or "").strip() or _extract_setting(text, defaults["setting"])
    time_of_day = str(hint.get("time") or "").strip() or _extract_time(text, defaults["time"])
    shot = str(hint.get("shot") or "").strip() or defaults["shot"]
    camera_intent = str(hint.get("camera_angle") or hint.get("camera_intent") or "").strip() or defaults["camera_intent"]
    emotion_state = str(hint.get("emotion_state") or "").strip() or _extract_emotion(text, defaults["emotion_state"])
    key_objects = hint.get("key_objects") if isinstance(hint.get("key_objects"), list) else _extract_key_objects(text)
    must_show = hint.get("must_show") if isinstance(hint.get("must_show"), list) else []
    if not must_show:
        must_show = [action]
        must_show.extend(key_objects[:2])
    must_not_show = hint.get("must_not_show") if isinstance(hint.get("must_not_show"), list) else []
    if not must_not_show:
        must_not_show = ["generic portrait", "unrelated location", "abstract mood-only shot"]
    continuity_mode = str(hint.get("continuity_mode") or "").strip().lower() or "same_subject_new_action"
    transition_motivation = str(hint.get("transition_motivation") or "").strip() or "same event progression"
    anchor_subject = str(hint.get("anchor_subject") or subject).strip() or subject
    anchor_setting = str(hint.get("anchor_setting") or setting).strip() or setting
    text_policy = infer_text_policy(narration=narration, on_screen_text=str(hint.get("on_screen_text") or ""), visual_hint=hint.get("text_policy") if isinstance(hint.get("text_policy"), dict) else hint)
    return {
        "subject": subject,
        "action": action,
        "setting": setting,
        "time": time_of_day,
        "shot": shot,
        "camera_angle": camera_intent,
        "camera_intent": camera_intent,
        "emotion_state": emotion_state,
        "key_objects": [str(x).strip() for x in key_objects if str(x).strip()][:4],
        "must_show": [str(x).strip() for x in must_show if str(x).strip()][:5],
        "must_not_show": [str(x).strip() for x in must_not_show if str(x).strip()][:5],
        "continuity_mode": continuity_mode,
        "transition_motivation": transition_motivation,
        "anchor_subject": anchor_subject,
        "anchor_setting": anchor_setting,
        "text_policy": text_policy,
    }


def scene_prompt_from_semantics(*, idx: int, style: str, narration: str, semantics: dict | None, aspect: str = "landscape") -> str:
    sem = semantics if isinstance(semantics, dict) else {}
    key_objects = ", ".join([str(x).strip() for x in list(sem.get("key_objects") or []) if str(x).strip()])
    must_show = "; ".join([str(x).strip() for x in list(sem.get("must_show") or []) if str(x).strip()])
    emotion_state = str(sem.get("emotion_state") or "真实克制的情绪").strip()
    text_policy = sem.get("text_policy") if isinstance(sem.get("text_policy"), dict) else {}
    text_mode = str(text_policy.get("mode") or "forbid").strip().lower()
    text_rule = ""
    if text_mode == "forbid":
        text_rule = "no readable text, no subtitles, no logos, no watermark, no UI words"
    elif text_mode == "incidental":
        text_rule = "if text appears on objects, keep it blurred, partial, non-readable, and not the visual focus"
    elif text_mode == "overlay":
        placement = str(text_policy.get("placement") or "top").strip().lower() or "top"
        text_rule = f"leave clean negative space at the {placement} for later overlay text; do not render text into the image"
    elif text_mode == "in_scene_required":
        text_rule = "show scene text only as part of the object itself, placed naturally, without floating subtitle-style text"
    parts = [
        str(sem.get("subject") or "真实人物").strip(),
        str(sem.get("action") or narration or "具体动作瞬间").strip(),
        str(sem.get("setting") or "真实场景").strip(),
        str(sem.get("time") or "自然光环境").strip(),
        str(sem.get("shot") or "medium cinematic shot").strip(),
        str(sem.get("camera_angle") or "").strip(),
        key_objects,
        f"emotion: {emotion_state}" if emotion_state else "",
        f"must show: {must_show}" if must_show else "",
        text_rule,
    ]
    setting_value = str(sem.get("setting") or "").strip()
    if setting_value and "古代" in setting_value and "古代场景" not in setting_value:
        parts.append("古代场景")
    continuity_mode = str(sem.get("continuity_mode") or "").strip().lower()
    if continuity_mode == "same_place_new_angle":
        parts.append("same room, same background identity, different framing angle")
    detail = ", ".join([p for p in parts if p]).strip(" ,")
    effective_style = style
    if "cinematic realism" in style.lower() and "chinese" not in style.lower():
        effective_style = f"Chinese {style}".strip()
    frame_ratio = "vertical 9:16" if str(aspect or "").strip().lower() == "portrait" else "horizontal 16:9"
    frame_guidance = "tall cinematic framing with safe top and bottom margins" if frame_ratio == "vertical 9:16" else "wide cinematic framing with safe side margins"
    return ", ".join(
        [
            detail,
            f"scene {int(idx)}",
            frame_ratio,
            frame_guidance,
            effective_style,
            "photorealistic",
            "real human expression",
            "natural lighting",
            "do not replace the described event with generic mood imagery",
        ]
    )


def scene_negative_from_semantics(semantics: dict | None) -> str:
    sem = semantics if isinstance(semantics, dict) else {}
    vals = [str(x).strip() for x in list(sem.get("must_not_show") or []) if str(x).strip()]
    text_policy = sem.get("text_policy") if isinstance(sem.get("text_policy"), dict) else {}
    text_mode = str(text_policy.get("mode") or "forbid").strip().lower()
    if text_mode == "forbid":
        vals.extend(["text", "subtitle", "caption", "logo", "watermark", "letters", "readable words", "ui overlay"])
    elif text_mode == "incidental":
        vals.extend(["large readable text", "floating subtitle text", "dominant typography", "clear ui overlay"])
    elif text_mode == "overlay":
        vals.extend(["text", "subtitle", "caption", "logo", "watermark", "readable words", "embedded typography"])
    return ", ".join(vals)
