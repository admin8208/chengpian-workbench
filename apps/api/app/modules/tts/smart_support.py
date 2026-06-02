import json
import re

from app.channel_profiles import channel_profile
from app.db import session_scope
from app.llm_client import LlmChatMessage, ollama_chat_json, openai_compat_chat_json
from app.llm_service import get_api_key, get_default_provider
from app.modules.tts.offline import piper_models_dir

from .smart_types import SmartTtsSegment


def _track_voice_profile(track_key: str) -> dict:
    profile = channel_profile(track_key)
    tts = profile.get("tts_profile") if isinstance(profile.get("tts_profile"), dict) else {}
    return {
        "edge_voices": [str(x) for x in (tts.get("edge_voices") or []) if str(x).strip()],
        "base_tempo": float(tts.get("base_tempo", 1.01) or 1.01),
        "base_pitch": float(tts.get("base_pitch", 1.0) or 1.0),
        "base_rate": str(tts.get("base_rate") or "+5%"),
        "pause_s": float(tts.get("pause_s", 0.07) or 0.07),
    }


def _extract_emphasis_words(text: str, emotion: str) -> list[tuple[str, str]]:
    t = (text or "").strip()
    if not t:
        return []
    em = (emotion or "neutral").strip().lower()
    results: list[tuple[str, str]] = []
    strong_patterns = [
        r"(真正|偏偏|居然|竟然|根本|绝对|完全|特别|非常|极其)",
        r"(最重要|最关键|说白了|问题是|结果)",
        r"(难道|怎么可能|凭什么|怎么敢)",
        r"(第一次|唯一|从来|始终)",
        r"(必须|一定|务必|千万)",
        r"(爱|恨|死|崩溃|绝望|完美|极品)",
        r"(天哪|我的天|卧槽|我去|我的妈)",
    ]
    moderate_patterns = [
        r"(其实|后来|原来|直到|可是|但是|不过|只是|然而)",
        r"(没想到|居然|原来|直到今天|那一刻)",
        r"(更|最|太|真|好|超|挺|蛮|颇|甚|略)",
        r"(为什么|怎么|哪里|哪个|谁|什么)",
        r"(多少|几时|多久|多远|多高)",
    ]
    for pat in strong_patterns:
        m = re.search(pat, t)
        if m:
            word = m.group(1)
            level = "strong" if em in ("angry", "emphatic", "excited") else "moderate"
            results.append((word, level))
    for pat in moderate_patterns:
        m = re.search(pat, t)
        if m:
            word = m.group(1)
            if not any(w == word for w, _ in results):
                results.append((word, "moderate"))
    return results


def _escape_ssml(text: str) -> str:
    t = text.replace("&", "&amp;")
    t = t.replace("<", "&lt;")
    t = t.replace(">", "&gt;")
    t = t.replace('"', "&quot;")
    return t


def _build_ssml_text(text: str, emotion: str, rate: str, *, pitch_st: float = 0.0) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    emphases = _extract_emphasis_words(t, emotion)
    if not emphases:
        prosody_attrs = [f'rate="{rate}"']
        if abs(pitch_st) > 0.01:
            sign = "+" if pitch_st > 0 else ""
            prosody_attrs.append(f'pitch="{sign}{pitch_st:.1f}st"')
        em = (emotion or "neutral").strip().lower()
        vol_map = {
            "soft": "-10%", "sad": "-8%", "gentle": "-5%",
            "angry": "+15%", "excited": "+12%", "emphatic": "+8%",
            "tense": "+5%", "surprised": "+10%",
        }
        if em in vol_map:
            prosody_attrs.append(f'volume="{vol_map[em]}"')
        attrs_str = " ".join(prosody_attrs)
        return f"<speak><prosody {attrs_str}>{_escape_ssml(t)}</prosody></speak>"
    result = t
    emph_sorted = sorted(emphases, key=lambda x: t.find(x[0]), reverse=True)
    for word, level in emph_sorted:
        tag = f'<emphasis level="{level}">{word}</emphasis>'
        result = result.replace(word, tag, 1)
    prosody_attrs = [f'rate="{rate}"']
    if abs(pitch_st) > 0.01:
        sign = "+" if pitch_st > 0 else ""
        prosody_attrs.append(f'pitch="{sign}{pitch_st:.1f}st"')
    em = (emotion or "neutral").strip().lower()
    vol_map = {
        "soft": "-10%", "sad": "-8%", "gentle": "-5%",
        "angry": "+15%", "excited": "+12%", "emphatic": "+8%",
        "tense": "+5%", "surprised": "+10%",
    }
    if em in vol_map:
        prosody_attrs.append(f'volume="{vol_map[em]}"')
    attrs_str = " ".join(prosody_attrs)
    return f"<speak><prosody {attrs_str}>{_escape_ssml(result)}</prosody></speak>"


def _intra_sentence_pause(text: str, emotion: str, track_key: str) -> tuple[float, int]:
    t = (text or "").strip()
    em = (emotion or "neutral").strip().lower()
    k = (track_key or "").strip().lower()
    total_pause = 0.0
    break_count = 0
    comma_count = t.count('，') + t.count(',')
    if comma_count > 0:
        base_comma = 0.04
        if em in ("sad", "gentle", "soft"):
            base_comma = 0.055
        elif em in ("angry", "excited", "tense"):
            base_comma = 0.03
        elif em == "serious":
            base_comma = 0.05
        total_pause += min(0.25, comma_count * base_comma)
        break_count += min(comma_count, 3)
    semicolon_count = t.count('；') + t.count(';')
    if semicolon_count > 0:
        total_pause += min(0.20, semicolon_count * 0.08)
        break_count += min(semicolon_count, 2)
    ellipsis_matches = re.findall(r"\.{3,}|…+", t)
    if ellipsis_matches:
        base_ellipsis = 0.25
        if em in ("sad", "dramatic"):
            base_ellipsis = 0.35
        elif em in ("excited", "surprised"):
            base_ellipsis = 0.18
        total_pause += len(ellipsis_matches) * base_ellipsis
        break_count += len(ellipsis_matches)
    dash_count = t.count('——') + t.count('--')
    if dash_count > 0:
        total_pause += min(0.20, dash_count * 0.10)
        break_count += min(dash_count, 2)
    if k == "emotion":
        total_pause *= 1.2
    elif k == "family_cn":
        total_pause *= 0.9
    return min(total_pause, 0.6), min(break_count, 8)


def _natural_pause_bonus(text: str, track_key: str) -> float:
    t = (text or "").strip()
    k = (track_key or "").strip().lower()
    bonus = 0.0
    bonus += min(0.12, t.count("，") * 0.012 + t.count(",") * 0.010)
    bonus += min(0.08, t.count("；") * 0.02 + t.count(";") * 0.02)
    bonus += min(0.18, len(re.findall(r"\.{3,}|…+", t)) * 0.06)
    bonus += min(0.12, t.count("。") * 0.015 + t.count("！") * 0.02 + t.count("？") * 0.02)
    if re.search(r"(结果|但是|可是|后来|原来|问题是|偏偏|直到)", t):
        bonus += 0.02
    if k == "family_cn" and re.search(r"(家里人|父母|妈妈|爸爸|亲戚|一家人)", t):
        bonus += 0.02
    if k == "history" and re.search(r"(史料|诏书|文书|档案|地图|器物)", t):
        bonus += 0.02
    return min(0.25, bonus)


def _parse_rate_pct(rate: str) -> int:
    s = str(rate or "").strip()
    m = re.match(r"^([+-]?)(\d+)%$", s)
    if not m:
        return 0
    sign = -1 if m.group(1) == "-" else 1
    return int(m.group(2)) * sign


def _fmt_rate_pct(val: int) -> str:
    return f"{int(val):+d}%"


def _merge_rate(base_rate: str, hint_rate: str) -> str:
    base = _parse_rate_pct(base_rate)
    hint = _parse_rate_pct(hint_rate)
    merged = base + hint
    merged = max(-25, min(65, merged))
    return _fmt_rate_pct(merged)


def _emphasis_adjustment(text: str, track_key: str) -> tuple[float, float, str]:
    t = (text or "").strip()
    k = (track_key or "").strip().lower()
    tempo = 1.0
    pitch = 1.0
    rate = "+0%"
    if re.search(r"(真正关键|问题是|偏偏|没想到)", t):
        tempo *= 0.995
        pitch *= 1.003
        rate = "-1%"
    if k == "history" and re.search(r"(其实|真正|偏偏|直到今天)", t):
        tempo *= 0.995
        rate = "-1%"
    elif k == "career" and re.search(r"(结果他来一句|问题是|最离谱的是)", t):
        tempo *= 1.003
        pitch *= 1.002
        rate = "+1%"
    elif k == "emotion" and re.search(r"(后来|原来|可她真正想说的是)", t):
        tempo *= 0.997
        pitch *= 1.002
        rate = "-1%"
    elif k == "family_cn" and re.search(r"(你以为|说白了|可她真正想说的是)", t):
        tempo *= 0.997
        rate = "-1%"
    return tempo, pitch, rate


def _is_drama_like(*, title: str, scenes: list[tuple[int, str]], scene_meta_json: list[str]) -> bool:
    t = (title or "").strip()
    txt = "\n".join([(n or "").strip() for _idx, n in scenes])
    try:
        for mj in scene_meta_json[:3]:
            m = json.loads(mj or "{}")
            fmt = str(((m.get("intent") or {}).get("format")) or "").strip().lower()
            if fmt in ("rant_drama", "warm_story", "story_confession"):
                return True
    except Exception:
        pass
    if re.search(r"(老板|领导|同事|HR|甲方|客户|面试官)\s*[:：]", txt):
        return True
    if txt.count("：") >= 2 and len(txt) >= 40:
        return True
    if re.search(r"[\"“].+?[\"”]", txt):
        return True
    if re.search(r"(我\s*(心想|内心|OS)|他\s*(说|回)|我\s*(说|回))", txt):
        return True
    if re.search(r"(短剧|对话|吵架|互怼|PUA|背锅)", t):
        return True
    return False


def is_drama_like(*, title: str, scenes: list[tuple[int, str]], scene_meta_json: list[str]) -> bool:
    return _is_drama_like(title=title, scenes=scenes, scene_meta_json=scene_meta_json)


def _semantic_join(prev: str, cur: str, *, max_len: int) -> bool:
    p = (prev or "").strip()
    c = (cur or "").strip()
    if not p or not c:
        return False
    if len(p) <= 8 or len(c) <= 8:
        return len(p + c) <= max_len
    if re.match(r"^(所以|但|但是|不过|可是|后来|然后|其实|而且|只是|直到|原来|结果|于是|甚至|反而|同时|接着|并且|尤其是)", c):
        return len(p + c) <= max_len
    if re.search(r"(不是|并不是|不只是|不光是|既不是|你以为|如果|因为|只有|除非|直到|越|既然|虽然|哪怕|即使|表面上)$", p):
        return True
    if re.match(r"^(而是|其实|才|就|也|却|还|反而|那|这才|这时候|但实际上|而且|所以)", c):
        return True
    if re.search(r"(不是.+而是|你以为.+其实|表面上.+但|如果.+就|因为.+所以|直到.+才|越.+越|虽然.+但是)", p + c):
        return True
    return False


def _spoken_chunks(text: str, *, max_len: int = 34, subtitle_mode: bool = False) -> list[str]:
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    if not t:
        return []
    primary = [x.strip() for x in re.split(r"(?<=[。！？!?])\s*", t) if x.strip()]
    merged: list[str] = []
    buf = ""
    for part in primary:
        if not buf:
            buf = part
            continue
        if _semantic_join(buf, part, max_len=max_len):
            buf += part
        else:
            merged.append(buf)
            buf = part
    if buf:
        merged.append(buf)
    final: list[str] = []
    for seg in merged:
        seg = seg.strip()
        if not seg:
            continue
        raw_subparts = [x.strip() for x in re.split(r"(?<=[；;：:])\s*", seg) if x.strip()]
        if len(raw_subparts) <= 1:
            raw_subparts = [x.strip() for x in re.split(r"(?<=[，,])\s*", seg) if x.strip()]
        if len(raw_subparts) <= 1:
            final.append(seg)
            continue
        local = ""
        for sp in raw_subparts:
            if not local:
                local = sp
                continue
            local_max = 22 if subtitle_mode else max_len
            if _semantic_join(local, sp, max_len=local_max) or len(local + sp) <= local_max:
                local += sp
            else:
                final.append(local)
                local = sp
        if local:
            final.append(local)
    return [x.strip() for x in final if x.strip()]


def _split_sentences(s: str) -> list[str]:
    t = (s or "").strip()
    if not t:
        return []
    t = re.sub(r"\s+", " ", t)
    return _spoken_chunks(t, max_len=34, subtitle_mode=False)


def _oralize_text(text: str) -> str:
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    if not t:
        return ""
    swaps = {
        "需要注意的是": "要注意的是",
        "值得注意的是": "要注意的是",
        "并且": "而且",
        "因此": "所以",
        "然而": "但是",
        "例如": "比如",
        "事实上": "其实",
        "某种程度上": "说白了",
        "与此同时": "同时",
    }
    for a, b in swaps.items():
        t = t.replace(a, b)
    t = re.sub(r"第\d+个关键点[:：]\s*", "", t)
    t = re.sub(r"(推进情节/信息|给一个具体细节或例子)", "", t)
    t = re.sub(r"(很多人不知道|不得不说|你会发现|其实你会发现)", "", t)
    t = re.sub(r"^(所以|但是|不过|然后|后来|结果)[，,:：]?", "", t)
    t = re.sub(r"([，。！？!?])\1+", r"\1", t)
    t = re.sub(r"\s+", "", t)
    return t


def _de_ai_oral_text(text: str) -> str:
    t = _oralize_text(text)
    if not t:
        return ""
    reps = [
        ("说白了，", ""),
        ("说白了", ""),
        ("其实，", ""),
        ("其实", ""),
        ("你慢慢就明白了，", ""),
        ("值得注意的是", "要注意的是"),
        ("需要注意的是", "要注意的是"),
        ("这才是重点。", "这才是关键。"),
        ("这就是证据。", "证据就在这。"),
        ("真正的底气，是", "底气，其实就是"),
        ("不可替代性才是", "不可替代，才是"),
    ]
    for a, b in reps:
        t = t.replace(a, b)
    t = re.sub(r"(很多人不知道|某种程度上|总的来说|综上所述|换句话说)", "", t)
    t = re.sub(r"^(首先|其次|最后|总之)[，,:：]?", "", t)
    t = re.sub(r"([，。！？!?])\1+", r"\1", t)
    t = re.sub(r"\s+", "", t)
    return t.strip("，, ")


def _fallback_segments(scenes: list[tuple[int, str]]) -> list[SmartTtsSegment]:
    segs: list[SmartTtsSegment] = []
    for idx, nar in scenes:
        lines = _split_sentences(_oralize_text(nar))
        if not lines:
            continue
        for ln in lines:
            pace = "normal"
            emotion = "neutral"
            if len(ln) <= 6:
                pace = "very_slow"
            elif len(ln) <= 12:
                pace = "slow"
            elif len(ln) >= 34:
                pace = "fast"
            elif len(ln) >= 26:
                pace = "very_fast"
            if re.search(r"(为什么|凭什么|怎么会|难道|不是吗|对吗)", ln):
                emotion = "emphatic"
            elif re.search(r"(难过|委屈|失望|心软|舍不得|遗憾|哭泣|泪|伤痛|崩溃)", ln):
                emotion = "soft"
            elif re.search(r"(生气|愤怒|恼火|气死了|凭什么|滚|去你的)", ln):
                emotion = "angry"
            elif re.search(r"(开心|高兴|兴奋|太好了|哈哈|棒|赞|完美)", ln):
                emotion = "excited"
            elif re.search(r"(惊讶|没想到|居然|竟然|真的吗|天哪|吓人)", ln):
                emotion = "surprised"
            elif re.search(r"(悲伤|悲痛|哀伤|心碎|可怜|心疼|寂寞)", ln):
                emotion = "sad"
            elif re.search(r"(温柔|轻声|柔软|细腻|贴心|温暖|呵护)", ln):
                emotion = "gentle"
            elif re.search(r"(严肃|认真|郑重|警告|注意|提醒)", ln):
                emotion = "serious"
            elif re.search(r"(紧张|焦虑|不安|担心|害怕|恐惧|颤抖)", ln):
                emotion = "tense"
            elif re.search(r"(安慰|建议|记住|最好|先|然后|复盘|总结)", ln):
                emotion = "calm"
            if re.search(r"(其实|后来|原来|直到|慢慢|只是)", ln) and emotion == "neutral":
                emotion = "calm"
            if re.search(r"(怎么办|怎么办啊|救命|帮帮我)", ln):
                emotion = "tense"
            if re.search(r"(好吧|那好吧|随便|算了|无所谓)", ln):
                emotion = "soft"
            m = re.match(r"^(老板|领导|同事|HR|客户|面试官|我)\s*[:：]\s*(.+)$", ln)
            if m:
                segs.append(SmartTtsSegment(scene_idx=int(idx), speaker=m.group(1), text=m.group(2).strip(), pace=pace, emotion=emotion))
            else:
                segs.append(SmartTtsSegment(scene_idx=int(idx), speaker="旁白", text=ln, pace=pace, emotion=emotion))
    return segs


def _style_adjustments(emotion: str, pace: str, *, track_key: str = "", text: str = "", speaker: str = "") -> tuple[float, float, str, float]:
    em = (emotion or "neutral").strip().lower()
    pc = (pace or "normal").strip().lower()
    prof = _track_voice_profile(track_key)
    tempo = float(prof.get("base_tempo") or 1.0)
    pitch = float(prof.get("base_pitch") or 1.0)
    rate = str(prof.get("base_rate") or "+0%")
    pause_s = float(prof.get("pause_s") or 0.08)
    sp = str(speaker or "").strip()
    narrator_like = sp in ("", "旁白", "叙述", "narrator")
    if narrator_like:
        tempo *= 0.99
        rate = _merge_rate(rate, "-2%")
        pause_s = max(pause_s, 0.085)
    else:
        tempo *= 0.98
        rate = _merge_rate(rate, "-8%")
        pause_s = max(pause_s, 0.08)
    if pc == "very_slow":
        tempo *= 0.92
        rate = _merge_rate(rate, "-8%")
        pause_s = max(pause_s, 0.12)
    elif pc == "slow":
        tempo *= 0.96
        rate = _merge_rate(rate, "-4%")
        pause_s = max(pause_s, 0.095)
    elif pc == "fast":
        tempo *= 1.03
        rate = _merge_rate(rate, "+4%")
        pause_s = 0.04
    elif pc == "very_fast":
        tempo *= 1.06
        rate = _merge_rate(rate, "+8%")
        pause_s = 0.03
    if em == "soft":
        tempo *= 0.95
        pitch *= 1.02
        pause_s = max(pause_s, 0.10)
        rate = _merge_rate(rate, "+4%")
    elif em == "tense":
        tempo *= 1.06
        pitch *= 0.98
        rate = _merge_rate(rate, "+12%")
        pause_s = max(pause_s, 0.05)
    elif em == "emphatic":
        tempo *= 1.04
        pitch *= 1.03
        pause_s = max(pause_s, 0.06)
        rate = _merge_rate(rate, "+10%")
    elif em == "calm":
        tempo *= 0.98
        rate = _merge_rate(rate, "-2%")
        pause_s = max(pause_s, 0.085)
    elif em == "excited":
        tempo *= 1.10
        pitch *= 1.04
        rate = _merge_rate(rate, "+15%")
        pause_s = max(pause_s, 0.04)
    elif em == "sad":
        tempo *= 0.90
        pitch *= 0.96
        rate = _merge_rate(rate, "-3%")
        pause_s = max(pause_s, 0.14)
    elif em == "surprised":
        tempo *= 1.05
        pitch *= 1.05
        rate = _merge_rate(rate, "+8%")
        pause_s = max(pause_s, 0.03)
    elif em == "angry":
        tempo *= 1.08
        pitch *= 0.95
        rate = _merge_rate(rate, "+14%")
        pause_s = max(pause_s, 0.035)
    elif em == "gentle":
        tempo *= 0.93
        pitch *= 1.03
        pause_s = max(pause_s, 0.11)
    elif em == "serious":
        tempo *= 1.02
        pitch *= 0.98
        rate = _merge_rate(rate, "+6%")
        pause_s = max(pause_s, 0.055)
    if track_key == "emotion":
        if narrator_like:
            pitch = 1.0 + ((pitch - 1.0) * 0.35)
            tempo = 1.0 + ((tempo - 1.0) * 0.7)
            pause_s = max(pause_s, 0.10)
        else:
            pitch = 1.0 + ((pitch - 1.0) * 0.25)
            tempo = 1.0 + ((tempo - 1.0) * 0.5)
            pause_s = max(pause_s, 0.14)
        if em == "soft":
            tempo *= 0.96
            pause_s = max(pause_s, 0.18)
        elif em == "tense":
            tempo *= 1.03
            pause_s = max(pause_s, 0.12)
        elif em == "emphatic":
            tempo *= 0.97
            pause_s = max(pause_s, 0.14)
        elif em == "excited":
            tempo *= 1.02
            pause_s = max(pause_s, 0.08)
        elif em == "sad":
            tempo *= 0.95
            pause_s = max(pause_s, 0.20)
        elif em == "surprised":
            tempo *= 1.01
            pause_s = max(pause_s, 0.06)
        elif em == "angry":
            tempo *= 1.04
            pause_s = max(pause_s, 0.07)
        elif em == "gentle":
            tempo *= 0.94
            pause_s = max(pause_s, 0.16)
        elif em == "serious":
            pause_s = max(pause_s, 0.09)
    et, ep, er = _emphasis_adjustment(text, track_key)
    tempo *= et
    pitch *= ep
    if er != "+0%":
        rate = _merge_rate(rate, er)
    pause_s += _natural_pause_bonus(text, track_key)
    return tempo, pitch, rate, pause_s


def _llm_segments(*, title: str, scenes: list[tuple[int, str]], llm_cfg: dict) -> list[SmartTtsSegment]:
    base_url = str(llm_cfg.get("base_url") or "")
    model = str(llm_cfg.get("model") or "")
    api_key = str(llm_cfg.get("api_key") or "")
    provider_type = str(llm_cfg.get("type") or "")
    if not base_url or not model:
        return []
    sys = (
        "你是短视频配音导演。把每个镜头的旁白改写为可表演的配音分段。\n"
        "只返回 STRICT JSON，不要任何多余文字。\n"
        'Schema: {"segments": [{"scene_idx": int, "speaker": str, "text": str, "pace": "very_slow|slow|normal|fast|very_fast", "emotion": str}] }\n'
        "emotion可选值: neutral|soft|tense|emphatic|calm|excited|sad|surprised|angry|gentle|serious\n"
        "pace可选值: very_slow(极慢-深情/悲伤)|slow(慢-温柔/讲述)|normal(正常)|fast(快-兴奋/紧张)|very_fast(极快-激动/争吵)\n"
        "规则：\n"
        "- 根据内容自动决定是否需要多角色；如果是剧情/对话/吐槽短剧，尽量 2-4 个 speaker 交替；如果是干货讲解，可以只用旁白。\n"
        "- speaker 用简短中文：旁白/我/老板/领导/同事/HR/客户/面试官 等；可自定义但保持一致。\n"
        "- text 要口语化、自然讲述，不要播音腔，不要喊。\n"
        "- 去掉 AI 套话：不要出现 很多人不知道 / 其实你会发现 / 值得注意的是 / 需要注意的是 / 第N个关键点。\n"
        "- 避免总结腔、讲课腔、播报腔，像真人在镜头前说话。\n"
        "- 优先保持自然语言片段，不要为了短而机械切碎；在语义转折点自然停顿。\n"
        "- 当句子里出现 结果/可是/其实/问题是/后来/原来 这类词时，让语气更有讲述感。\n"
        "- 不要出现括号里的舞台说明；情绪用 emotion 字段表达即可。\n"
    )
    user_lines = [f"标题：{title}", "镜头旁白："]
    for idx, nar in scenes:
        user_lines.append(f"{idx}: {nar}")
    messages = [LlmChatMessage(role="system", content=sys), LlmChatMessage(role="user", content="\n".join(user_lines))]
    if provider_type == "ollama":
        obj = ollama_chat_json(base_url=base_url, model=model, messages=messages)
    elif provider_type == "openai_compat":
        if not api_key:
            return []
        obj = openai_compat_chat_json(base_url=base_url, api_key=api_key, model=model, messages=messages)
    else:
        return []
    segs = obj.get("segments")
    if not isinstance(segs, list):
        return []
    out: list[SmartTtsSegment] = []
    valid_paces = ("very_slow", "slow", "normal", "fast", "very_fast")
    valid_emotions = ("neutral", "soft", "tense", "emphatic", "calm", "excited", "sad", "surprised", "angry", "gentle", "serious")
    for it in segs:
        if not isinstance(it, dict):
            continue
        try:
            scene_idx = int(it.get("scene_idx") or 0)
        except Exception:
            scene_idx = 0
        speaker = str(it.get("speaker") or "旁白").strip() or "旁白"
        text = _de_ai_oral_text(str(it.get("text") or "").strip())
        if not scene_idx or not text:
            continue
        pace = str(it.get("pace") or "normal").strip().lower()
        if pace not in valid_paces:
            pace = "normal"
        emotion = str(it.get("emotion") or "neutral").strip()
        if emotion not in valid_emotions:
            emotion = "neutral"
        out.append(SmartTtsSegment(scene_idx=scene_idx, speaker=speaker, text=text, pace=pace, emotion=emotion))
    return out


def _voice_compatible_with_installed_engine(voice_id: str) -> bool:
    vid = (voice_id or "").strip()
    if not vid:
        return False
    try:
        cfg = piper_models_dir() / f"{vid}.onnx.json"
        if not cfg.exists() or cfg.stat().st_size <= 0:
            return False
        obj = json.loads(cfg.read_text(encoding="utf-8"))
        return str(obj.get("phoneme_type") or "").strip().lower() != "pinyin"
    except Exception:
        return False


def _installed_offline_voice_ids() -> list[str]:
    mdir = piper_models_dir()
    if not mdir.exists():
        return []
    ids: list[str] = []
    for p in sorted(mdir.glob("*.onnx")):
        vid = p.stem
        if not vid:
            continue
        cfg = mdir / f"{vid}.onnx.json"
        if not cfg.exists() or cfg.stat().st_size <= 0:
            continue
        if _voice_compatible_with_installed_engine(vid) and vid not in ids:
            ids.append(vid)
    return ids


def _speaker_alias(s: str) -> str:
    x = (s or "").strip()
    if not x or x in ("旁白", "叙述", "narrator"):
        return ""
    if x in ("老板", "领导", "同事", "我"):
        return x
    return x[:6]


def build_scene_captions_from_segments(segs: list[SmartTtsSegment]) -> dict[int, str]:
    by_scene: dict[int, list[SmartTtsSegment]] = {}
    for s in segs:
        by_scene.setdefault(int(s.scene_idx), []).append(s)
    out: dict[int, str] = {}
    for scene_idx, arr in by_scene.items():
        speakers = []
        for s in arr:
            sp = (s.speaker or "").strip()
            if sp and sp not in speakers:
                speakers.append(sp)
        multi = len([sp for sp in speakers if sp not in ("旁白", "叙述", "narrator")]) >= 2
        lines: list[str] = []
        for s in arr:
            tx = (s.text or "").strip()
            if not tx:
                continue
            if multi:
                alias = _speaker_alias(s.speaker)
                lines.append(f"{alias}：{tx}" if alias else tx)
            else:
                lines.append(tx)
        out[int(scene_idx)] = "\n".join(lines).strip()
    return out


def resolve_llm_cfg() -> dict | None:
    llm_cfg: dict | None = None
    with session_scope() as session:
        prov = get_default_provider(session)
        if prov and prov.enabled and prov.default_model and prov.base_url:
            key = ""
            if prov.type == "openai_compat" and prov.id is not None:
                key = get_api_key(session, int(prov.id))
            if prov.type == "ollama" or (prov.type == "openai_compat" and key):
                llm_cfg = {"type": prov.type, "base_url": prov.base_url, "model": prov.default_model, "api_key": key}
    return llm_cfg
