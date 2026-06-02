import re

from app.llm_client import LlmChatMessage, LlmError, ollama_chat_json, openai_compat_chat_json
from app.material_policies import normalize_material_mode
from app.models import ChannelPack, LlmProvider
from app.prompts import (
    PROMPT_META_WRITER_REWRITE,
    build_rewrite_storyboard_messages,
    track_query_bias,
)
from app.storyboard_postprocess import (
    enrich_storyboard_continuity,
    normalize_storyboard_output,
    normalize_storyboard_scene_durations,
)
from app.storyboard_service import generate_storyboard_via_llm


_OPENING_CLICHE_PATTERNS = [
    r"^(?:哈喽|hello|hi)?大家好[，,。！!\s]*",
    r"^今天(?:想)?(?:跟|和)?大家聊聊[，,。！!\s]*",
    r"^今天我们来聊聊[，,。！!\s]*",
    r"^今天来聊聊[，,。！!\s]*",
    r"^这(?:一|一整)?期(?:视频|内容)?(?:我们)?(?:来)?(?:讲|说|聊聊?)[，,。！!\s]*",
    r"^本期(?:视频|内容)?(?:我们)?(?:来)?(?:讲|说|聊聊?)[，,。！!\s]*",
    r"^接下来(?:带|给)?大家(?:看|讲|说|聊聊?)[，,。！!\s]*",
    r"^下面(?:我们)?(?:来)?(?:讲|说|聊聊?)[，,。！!\s]*",
]

_PLATFORM_CLICHE_PATTERNS = [
    r"(?:记得|先)?(?:给我|给这条)?点(?:个)?赞(?:和)?收藏(?:一下)?",
    r"(?:先)?关注我(?:不迷路)?",
    r"(?:欢迎|也可以)?在评论区(?:留言|告诉我|聊聊|说说)",
    r"屏幕前的你",
    r"看到最后",
    r"建议(?:先)?收藏",
    r"建议(?:转发|分享)给",
]


def _strip_opening_cliches(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return ""
    changed = True
    while changed and s:
        changed = False
        for pattern in _OPENING_CLICHE_PATTERNS:
            nxt = re.sub(pattern, "", s, flags=re.IGNORECASE).strip()
            if nxt != s:
                s = nxt.lstrip("，,。！!？?：:；;、 ")
                changed = True
    return s


def _strip_platform_cliches(text: str) -> str:
    s = str(text or "")
    for pattern in _PLATFORM_CLICHE_PATTERNS:
        s = re.sub(pattern, "", s, flags=re.IGNORECASE)
    return s.strip()


def storyboard_duration_profile(pack: ChannelPack, cfg: dict | None = None, *, render_cfg: dict | None = None) -> dict:
    cfg_obj = cfg if isinstance(cfg, dict) else {}
    rcfg = render_cfg if isinstance(render_cfg, dict) else {}

    def _as_int(v, d: int) -> int:
        try:
            return int(v)
        except Exception:
            return d

    def _as_float(v, d: float) -> float:
        try:
            return float(v)
        except Exception:
            return d

    scene_count = _as_int(cfg_obj.get("scene_count", 8), 8)
    scene_count = _as_int(rcfg.get("scene_count", scene_count), scene_count)
    scene_count = max(4, min(12, scene_count))

    base_dur = _as_float(cfg_obj.get("scene_duration_sec", 6), 6.0)
    base_dur = _as_float(rcfg.get("scene_duration_sec", base_dur), base_dur)
    base_dur = max(2.0, min(15.0, base_dur))

    min_total = _as_float(cfg_obj.get("target_min_sec", 0.0), 0.0)
    max_total = _as_float(cfg_obj.get("target_max_sec", 0.0), 0.0)
    target_total = _as_float(cfg_obj.get("target_sec", 0.0), 0.0)

    min_total = _as_float(rcfg.get("target_min_sec", min_total), min_total)
    max_total = _as_float(rcfg.get("target_max_sec", max_total), max_total)
    target_total = _as_float(rcfg.get("target_sec", target_total), target_total)

    if str(getattr(pack, "key", "") or "").strip().lower() == "emotion":
        if min_total <= 0:
            min_total = 30.0
        if max_total <= 0:
            max_total = 40.0
        if target_total <= 0:
            target_total = 35.0
        base_dur = float(max(2.0, min(15.0, target_total / float(max(1, scene_count)))))

    if max_total > 0 and min_total > max_total:
        min_total, max_total = max_total, min_total
    if target_total <= 0 and max_total > 0 and min_total > 0:
        target_total = (min_total + max_total) / 2.0
    if target_total <= 0 and scene_count > 0:
        target_total = float(scene_count) * float(base_dur)

    if min_total > 0 and target_total < min_total:
        target_total = min_total
    if max_total > 0 and target_total > max_total:
        target_total = max_total

    return {
        "aspect": str(rcfg.get("aspect") or "landscape").strip().lower() or "landscape",
        "scene_count": int(scene_count),
        "scene_duration_sec": float(base_dur),
        "target_min_sec": float(min_total) if min_total > 0 else 0.0,
        "target_max_sec": float(max_total) if max_total > 0 else 0.0,
        "target_sec": float(target_total),
    }


def gen_script_and_scenes(topic: str, pack: ChannelPack, *, render_cfg: dict | None = None) -> tuple[str, list[dict]]:
    cfg = pack.config()
    prof = storyboard_duration_profile(pack, cfg, render_cfg=render_cfg)
    n = int(prof.get("scene_count", 8))
    base_dur = float(prof.get("scene_duration_sec", 6.0))
    style = str(cfg.get("style", "cinematic realism"))
    aspect = str(prof.get("aspect") or "landscape").strip().lower() or "landscape"

    if pack.key == "history":
        hook = f"说到{topic}，很多人先记住的是表面结论，真正有意思的往往藏在细节里。"
        ending = "再把线索顺一遍，你会发现，决定判断的往往不是大事件本身。"
    elif pack.key == "family_cn":
        hook = f"说到{topic}，很多家庭不是没有感情，而是常常卡在不会好好说话。"
        ending = "把那句话背后的情绪看清楚，很多僵着的关系才有可能慢慢松开。"
    elif pack.key == "emotion":
        hook = f"说到{topic}，真正让人难受的，往往不是一件大事，而是那些反复出现的小瞬间。"
        ending = "等你把这些细节连起来看，很多委屈就不再只是情绪本身。"
    elif pack.key == "career":
        hook = f"说到{topic}，很多职场问题不是突然爆出来的，而是前面几个细节一直没人当回事。"
        ending = "把那个关键节点看明白，下次再遇到类似情况，处理会顺很多。"
    else:
        hook = f"说到{topic}，很多人第一眼看到的是结果，真正该盯住的往往是过程里的那一步。"
        ending = "把过程拆开来看，很多看似复杂的事其实会清楚很多。"

    script_lines = [hook]
    scenes: list[dict] = []
    for i in range(n):
        idx = i + 1
        if idx == 1:
            narration = hook
        elif idx == n:
            narration = ending
        else:
            narration = f"接着往下看，把{topic}里那个具体场景、动作变化或一句关键的话讲清楚。"

        script_lines.append(narration)
        frame_ratio = "vertical 9:16" if aspect == "portrait" else "horizontal 16:9"
        image_prompt = f"photorealistic, Chinese aesthetic, {style}, {frame_ratio}, scene {idx}, {topic}, natural lighting, realistic"
        scenes.append(
            {
                "idx": idx,
                "narration": narration,
                "image_prompt": image_prompt,
                "duration_sec": base_dur,
            }
        )

    script = "\n".join(script_lines)
    scenes = normalize_storyboard_scene_durations(scenes, target_sec=float(prof.get("target_sec", 0.0)))
    scenes = enrich_storyboard_continuity(scenes)
    return script, scenes


def de_ai_phrase(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return ""
    s = _strip_opening_cliches(s)
    reps = [
        ("很多人不知道，", ""),
        ("很多人不知道", ""),
        ("说白了，", ""),
        ("说白了", ""),
        ("真正的问题是，", "问题是，"),
        ("真正的问题是", "问题是"),
        ("说到底，", "其实，"),
        ("说到底", "其实"),
        ("其实你会发现，", "你会发现，"),
        ("其实你会发现", "你会发现"),
        ("关于", "说到"),
        ("第1个关键点：", ""),
        ("第2个关键点：", ""),
        ("第3个关键点：", ""),
        ("第4个关键点：", ""),
        ("第5个关键点：", ""),
        ("第6个关键点：", ""),
        ("第7个关键点：", ""),
        ("第8个关键点：", ""),
        ("推进情节/信息", "往下说"),
        ("给一个具体细节或例子", "细节就在这"),
        ("这就是证据。", "证据就在这。"),
        ("你会发现，", "你慢慢就明白了， "),
        ("90%的人第一步就做错了", "很多问题，一开始就埋下了"),
        ("记住这个小道理，今天就能用上", "把这层意思看明白，很多话就不会白受"),
    ]
    for a, b in reps:
        s = s.replace(a, b)
    s = _strip_platform_cliches(s)
    s = re.sub(r"第\d+个关键点[:：]\s*", "", s)
    s = re.sub(r"(围绕[^，。！？!?]{0,18}推进情节/信息)", "", s)
    s = re.sub(r"(给一个具体细节或例子)", "", s)
    s = re.sub(r"^(而且|另外|并且)，", "", s)
    s = re.sub(r"^(首先|其次|最后|总之|综上所述)[，,:：]", "", s)
    s = re.sub(r"(很多人不知道|你要知道|需要注意的是|值得注意的是|不得不说|某种程度上)", "", s)
    s = re.sub(r"^(咱们|我们)今天(?:就)?(?:来)?(?:讲|说|聊聊?)", "", s)
    s = re.sub(r"(其实|但是|所以|然后|后来|结果)(\1)+", r"\1", s)
    s = re.sub(r"([，。！？])\1+", r"\1", s)
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"([，。！？!?])([，。！？!?])", r"\2", s)
    s = s.lstrip("，,。！!？?：:；;、 ")
    if len(s) >= 10:
        parts = [x.strip() for x in re.split(r"(?<=[。！？!?])", s) if x.strip()]
        deduped: list[str] = []
        last_norm = ""
        for part in parts:
            part = _strip_opening_cliches(_strip_platform_cliches(part)).strip()
            if not part:
                continue
            norm = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", part)
            if norm and norm == last_norm:
                continue
            deduped.append(part)
            last_norm = norm
        if deduped:
            s = "".join(deduped)
    return s.strip(" ，")


def llm_generate_storyboard(
    topic: str,
    pack: ChannelPack,
    provider: LlmProvider,
    api_key: str,
    *,
    character_profile: str = "",
    workflow: str = "mix",
    render_cfg: dict | None = None,
    material_mode: str = "",
) -> tuple[str, list[dict]]:
    cfg = pack.config()
    prof = storyboard_duration_profile(pack, cfg, render_cfg=render_cfg)
    hook_style = str(cfg.get("hook_style", ""))
    return generate_storyboard_via_llm(
        topic=topic,
        pack=pack,
        provider=provider,
        api_key=api_key,
        character_profile=character_profile,
        workflow=workflow,
        duration_profile=prof,
        hook_style=hook_style,
        de_ai_phrase=de_ai_phrase,
        material_mode=normalize_material_mode(material_mode or (render_cfg or {}).get("material_mode")),
    )


def llm_rewrite_storyboard(
    source_text: str,
    pack: ChannelPack,
    provider: LlmProvider,
    api_key: str,
    *,
    character_profile: str = "",
    level: str = "medium",
    workflow: str = "mix",
    render_cfg: dict | None = None,
    material_mode: str = "",
) -> tuple[str, list[dict]]:
    src = (source_text or "").strip()
    if not src:
        raise LlmError("source_text empty")

    cp = (character_profile or "").strip()
    level = (level or "medium").strip().lower()
    if level not in ("safe", "medium", "strong"):
        level = "medium"

    cfg = pack.config()
    prof = storyboard_duration_profile(pack, cfg, render_cfg=render_cfg)
    base_dur = float(prof.get("scene_duration_sec", 6.0))
    visual_style = str(cfg.get("style", "cinematic realism"))
    negative = str(cfg.get("negative", ""))
    aspect = str((render_cfg or {}).get("aspect") or "landscape").strip().lower() or "landscape"
    msg = build_rewrite_storyboard_messages(
        pack=pack,
        workflow=workflow,
        source_text=src,
        level=level,
        character_profile=cp,
        prof=prof,
        visual_style=visual_style,
        negative=negative,
        aspect=aspect,
    )

    messages = [LlmChatMessage(role="system", content=msg.system), LlmChatMessage(role="user", content=msg.user)]
    model = (provider.default_model or "").strip()
    if provider.type == "ollama":
        obj = ollama_chat_json(base_url=provider.base_url, model=model, messages=messages)
    elif provider.type == "openai_compat":
        if not api_key:
            raise LlmError("API key not set")
        obj = openai_compat_chat_json(
            base_url=provider.base_url,
            api_key=api_key,
            model=model,
            messages=messages,
        )
    else:
        raise LlmError(f"unsupported provider type: {provider.type}")

    try:
        return normalize_storyboard_output(
            obj=obj,
            pack_key=str(pack.key or ""),
            topic=src[:24],
            base_dur=base_dur,
            target_sec=float(prof.get("target_sec", 0.0)),
            de_ai_phrase=de_ai_phrase,
            track_query_bias=track_query_bias(str(pack.key or "")),
            writer_name=PROMPT_META_WRITER_REWRITE,
            prompt_workflow=str(workflow or "mix").strip().lower() or "mix",
            default_image_prompt=(
                "photorealistic, Chinese aesthetic, cinematic realism, vertical 9:16, scene {idx}, {topic}, natural lighting, realistic"
                if aspect == "portrait"
                else "photorealistic, Chinese aesthetic, cinematic realism, horizontal 16:9, scene {idx}, {topic}, natural lighting, realistic"
            ),
            material_mode=normalize_material_mode(material_mode or (render_cfg or {}).get("material_mode")),
            intent_meta={},
        )
    except ValueError as e:
        raise LlmError(str(e))
