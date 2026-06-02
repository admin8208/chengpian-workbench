from app.intent_catalog import catalog_for_pack, select_template_for_intent
from app.llm_client import LlmChatMessage, LlmError, ollama_chat_json, openai_compat_chat_json
from app.prompts import (
    PROMPT_META_WRITER_GENERATE,
    build_ai_storyboard_messages,
    build_network_storyboard_messages,
    build_storyboard_repair_messages,
    collect_bad_storyboard_scenes,
    track_query_bias,
)
from app.storyboard_postprocess import normalize_storyboard_output


def _default_ai_image_prompt(*, topic: str, idx: int, pack_key: str, aspect: str = "landscape") -> str:
    subject = "真实人物"
    action = topic or "一个具体行为瞬间"
    setting = "真实场景"
    time_of_day = "自然光环境"
    shot = "medium cinematic shot"
    low = str(pack_key or "").strip().lower()
    if low == "emotion":
        subject = "关系中的两个人物"
        action = "沉默对视 或 欲言又止"
        setting = "家中或街头的真实生活场景"
        time_of_day = "傍晚或夜晚"
        shot = "close up emotional shot"
    elif low == "family_cn":
        subject = "家庭成员"
        action = "交谈 停顿 或 情绪对峙"
        setting = "客厅 饭桌 或 电话场景"
        time_of_day = "傍晚暖光"
        shot = "medium realistic shot"
    elif low == "history":
        subject = "历史人物或关键器物"
        action = "展示线索 对峙 或 行进"
        setting = "古代场景或历史空间"
        time_of_day = "白天或烛光夜晚"
        shot = "documentary medium close shot"
    elif low == "career":
        subject = "职场人物"
        action = "沟通 汇报 打字 或 停顿思考"
        setting = "办公室 会议室 或 通勤场景"
        time_of_day = "工作日白天或夜晚"
        shot = "medium handheld shot"
    frame_ratio = "vertical 9:16" if str(aspect or "").strip().lower() == "portrait" else "horizontal 16:9"
    frame_guidance = "tall cinematic framing with safe top and bottom margins" if frame_ratio == "vertical 9:16" else "wide cinematic framing with safe side margins"
    return ", ".join(
        [
            "photorealistic",
            "Chinese cinematic realism",
            frame_ratio,
            f"scene {idx}",
            subject,
            action,
            setting,
            time_of_day,
            shot,
            "natural lighting",
            "real human emotion",
            frame_guidance,
            "realistic",
            topic,
        ]
    )


def call_llm_json(*, provider, api_key: str, messages: list[LlmChatMessage], timeout_s: int = 600, max_tokens: int | None = None) -> dict:
    model = (provider.default_model or "").strip()
    if not model:
        raise LlmError("provider model is empty")
    if provider.type == "ollama":
        obj = ollama_chat_json(base_url=provider.base_url, model=model, messages=messages, timeout_s=timeout_s)
    elif provider.type == "openai_compat":
        if not api_key:
            raise LlmError("API key not set")
        obj = openai_compat_chat_json(
            base_url=provider.base_url,
            api_key=api_key,
            model=model,
            messages=messages,
            timeout_s=timeout_s,
            max_tokens=max_tokens,
        )
    else:
        raise LlmError(f"unsupported provider type: {provider.type}")
    if not isinstance(obj, dict):
        raise LlmError("LLM returned non-dict")
    return obj


def _default_intent_meta(pack_key: str, hook_style: str, material_mode: str) -> dict:
    catalog = catalog_for_pack(pack_key)
    return {
        "family": str(catalog.get("intents", [{}])[0].get("id", "") or "").strip(),
        "format": str(catalog.get("formats", [{}])[0].get("id", "") or "").strip(),
        "tone": "warm" if pack_key in ("emotion", "family_cn") else ("suspense" if pack_key == "history" else "sharp"),
        "roles": [],
        "conflict": "",
        "risk_flags": [],
        "template_id": "single_pass_template",
        "template_type": "single_pass",
        "hook_style": hook_style,
        "material_mode": material_mode,
    }


def _single_pass_messages(*, pack, workflow: str, topic: str, character_profile: str, n: int, base_dur: float, prof: dict, material_mode: str):
    mode = str(material_mode or "network").strip().lower() or "network"
    aspect = str((prof or {}).get("aspect") or "landscape").strip().lower() or "landscape"
    if mode == "ai":
        return build_ai_storyboard_messages(pack=pack, workflow=workflow, topic=topic, character_profile=character_profile, n=n, base_dur=base_dur, prof=prof, aspect=aspect)
    return build_network_storyboard_messages(pack=pack, workflow=workflow, topic=topic, character_profile=character_profile, n=n, base_dur=base_dur, prof=prof, aspect=aspect)


def _is_timeout_error(exc: Exception) -> bool:
    low = str(exc or "").strip().lower()
    return any(x in low for x in ("timeout", "timed out", "read timeout", "connect timeout"))


def _call_storyboard_once(*, provider, api_key: str, pack, workflow: str, topic: str, character_profile: str, n: int, base_dur: float, prof: dict, material_mode: str) -> dict:
    msg = _single_pass_messages(pack=pack, workflow=workflow, topic=topic, character_profile=character_profile, n=n, base_dur=base_dur, prof=prof, material_mode=material_mode)
    return call_llm_json(provider=provider, api_key=api_key, messages=[LlmChatMessage(role="system", content=msg.system), LlmChatMessage(role="user", content=msg.user)])


def _call_storyboard_with_retry(*, provider, api_key: str, pack, workflow: str, topic: str, character_profile: str, n: int, base_dur: float, prof: dict, material_mode: str) -> dict:
    try:
        return _call_storyboard_once(provider=provider, api_key=api_key, pack=pack, workflow=workflow, topic=topic, character_profile=character_profile, n=n, base_dur=base_dur, prof=prof, material_mode=material_mode)
    except Exception as exc:
        if not _is_timeout_error(exc):
            raise
    msg = _single_pass_messages(pack=pack, workflow=workflow, topic=topic, character_profile=character_profile, n=n, base_dur=base_dur, prof=prof, material_mode=material_mode)
    retry_user = f"{msg.user}\nLight retry mode: keep each scene simpler, shorter, and more direct. Avoid over-design and long reasoning."
    return call_llm_json(provider=provider, api_key=api_key, messages=[LlmChatMessage(role="system", content=msg.system), LlmChatMessage(role="user", content=retry_user)])


def generate_storyboard_via_llm(
    *,
    topic: str,
    pack,
    provider,
    api_key: str,
    character_profile: str = "",
    workflow: str = "mix",
    duration_profile: dict,
    hook_style: str = "",
    de_ai_phrase,
    material_mode: str = "network",
) -> tuple[str, list[dict]]:
    prof = duration_profile if isinstance(duration_profile, dict) else {}
    n = int(prof.get("scene_count", 8))
    base_dur = float(prof.get("scene_duration_sec", 6.0))
    mode = str(material_mode or "network").strip().lower() or "network"
    intent_meta = _default_intent_meta(str(pack.key or "").strip().lower(), hook_style, mode)
    template_obj = select_template_for_intent(pack.key, intent_family=str(intent_meta.get("family") or ""), format_id=str(intent_meta.get("format") or ""))
    if isinstance(template_obj, dict):
        intent_meta["template_id"] = str(template_obj.get("id", "") or intent_meta["template_id"])
        intent_meta["template_type"] = str(template_obj.get("type", "") or intent_meta["template_type"])
        intent_meta["hook_style"] = str(template_obj.get("hook_style", "") or intent_meta["hook_style"])

    obj = _call_storyboard_with_retry(
        provider=provider,
        api_key=api_key,
        pack=pack,
        workflow=workflow,
        topic=topic,
        character_profile=(character_profile or "").strip(),
        n=n,
        base_dur=base_dur,
        prof=prof,
        material_mode=mode,
    )

    try:
        bad = collect_bad_storyboard_scenes(obj.get("scenes") if isinstance(obj.get("scenes"), list) else [])
        if bad:
            msg = build_storyboard_repair_messages(
                pack=pack,
                topic=topic,
                intent_family=str(intent_meta.get("family") or ""),
                format_id=str(intent_meta.get("format") or ""),
                tone=str(intent_meta.get("tone") or ""),
                template_id=str(intent_meta.get("template_id") or ""),
                template_type=str(intent_meta.get("template_type") or ""),
                beats=[],
                bad_list=bad,
                storyboard_obj=obj,
            )
            obj2 = call_llm_json(provider=provider, api_key=api_key, messages=[LlmChatMessage(role="system", content=msg.system), LlmChatMessage(role="user", content=msg.user)])
            if isinstance(obj2, dict) and isinstance(obj2.get("scenes"), list) and obj2.get("script"):
                obj = obj2
    except Exception:
        pass

    try:
        return normalize_storyboard_output(
            obj=obj,
            pack_key=str(pack.key or ""),
            topic=topic,
            base_dur=base_dur,
            target_sec=float(prof.get("target_sec", 0.0)),
            de_ai_phrase=de_ai_phrase,
            track_query_bias=track_query_bias(str(pack.key or "")),
            writer_name=PROMPT_META_WRITER_GENERATE,
            prompt_workflow=str(workflow or "mix").strip().lower() or "mix",
            default_image_prompt=_default_ai_image_prompt(
                topic=topic,
                idx=1,
                pack_key=str(pack.key or ""),
                aspect=str(prof.get("aspect") or "landscape"),
            ).replace("scene 1", "scene {idx}"),
            intent_meta=intent_meta,
            material_mode=mode,
        )
    except ValueError as e:
        raise LlmError(str(e))
