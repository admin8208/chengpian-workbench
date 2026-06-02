
import html
import os
import re
import subprocess
from functools import lru_cache


_DISPLAY_PUNCT_RE = re.compile(r"[\u3000\s]*[，。！？；：、“”‘’（）()\[\]{}<>《》…—\-_,.!?;:'\"`~|\\/]+[\u3000\s]*")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\ufeff]")
_TTS_META_RE = re.compile(r"(?:\[(?:旁白|备注|说明|注|提示|音效|BGM|bgm|music|music cue)[^\]]*\]|（(?:旁白|备注|说明|注|提示|音效|BGM|bgm|music|music cue)[^）]*）|\((?:旁白|备注|说明|note|tips?|music|bgm)[^)]*\))")
_TTS_META_WORD_RE = re.compile(r"\b(?:提示|备注|说明|旁白|注释|注)\b[:：]?", re.IGNORECASE)


def clean_tts_text(text: str) -> str:
    txt = html.unescape(str(text or ""))
    txt = _ZERO_WIDTH_RE.sub("", txt)
    txt = _CONTROL_CHARS_RE.sub(" ", txt)
    txt = txt.replace("\r", " ").replace("\n", " ")
    txt = _TTS_META_RE.sub(" ", txt)
    txt = _TTS_META_WORD_RE.sub(" ", txt)
    txt = re.sub(r"[#*_`]+", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    txt = re.sub(r"([，。！？；：,.!?;:]){2,}", r"\1", txt)
    return txt[:5000].strip()


def clean_subtitle_display_text(text: str) -> str:
    txt = clean_tts_text(text)
    txt = _DISPLAY_PUNCT_RE.sub(" ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


@lru_cache(maxsize=1)
def _default_cjk_fontname() -> str:
    # Return a font family that is actually resolvable on the current host.
    if os.name == "nt":
        return "Microsoft YaHei"

    candidates = [
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "WenQuanYi Micro Hei",
        "Microsoft YaHei",
        "PingFang SC",
        "SimHei",
    ]
    for name in candidates:
        try:
            resolved = subprocess.run(
                ["fc-match", "-f", "%{family}\n", name],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            ).stdout.strip()
        except Exception:
            continue
        families = [part.strip() for part in resolved.split(",") if part.strip()]
        if name in families:
            return name

    return "sans-serif"


def vtt_to_srt(vtt: str) -> str:
    # edge-tts SubMaker emits WEBVTT with CRLF.
    lines = vtt.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    i = 0
    idx = 0

    # Skip header
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i < len(lines) and lines[i].strip().upper().startswith("WEBVTT"):
        i += 1

    while i < len(lines):
        # skip blank lines
        while i < len(lines) and lines[i].strip() == "":
            i += 1
        if i >= len(lines):
            break

        time_line = lines[i].strip()
        i += 1
        if "-->" not in time_line:
            continue
        start, end = [x.strip() for x in time_line.split("-->", 1)]
        start = start.replace(".", ",")
        end = end.replace(".", ",")

        text_lines: list[str] = []
        while i < len(lines) and lines[i].strip() != "":
            text_lines.append(lines[i])
            i += 1

        idx += 1
        out.append(str(idx))
        out.append(f"{start} --> {end}")
        txt = "\n".join(text_lines).strip()
        out.append(clean_subtitle_display_text(txt))
        out.append("")

    return "\n".join(out).strip() + "\n"


def subtitle_style_preset(key: str, *, aspect: str = "landscape") -> str:
    # Returned string is an ASS force_style fragment used by ffmpeg subtitles filter.
    # https://ffmpeg.org/ffmpeg-filters.html#subtitles
    # Colors are in ASS format: &HAABBGGRR
    # aspect is retained for API compatibility; rendering is landscape-only.

    if key == "emotion":
        return ",".join(
            [
                f"Fontname={_default_cjk_fontname()}",
                "Fontsize=22",
                "PrimaryColour=&H00FFFFFF",
                "OutlineColour=&H00000000",
                "BackColour=&H60000000",
                "BorderStyle=3",
                "Outline=1.4",
                "Shadow=0",
                "Alignment=2",
                "MarginV=32",
            ]
        )
    if key == "boxed":
        return ",".join(
            [
                f"Fontname={_default_cjk_fontname()}",
                "Fontsize=22",
                "PrimaryColour=&H00FFFFFF",
                "OutlineColour=&H00000000",
                "BackColour=&H80000000",
                "BorderStyle=3",
                "Outline=1.4",
                "Shadow=0",
                "Alignment=2",
                "MarginV=32",
            ]
        )
    if key == "clean":
        return ",".join(
            [
                f"Fontname={_default_cjk_fontname()}",
                "Fontsize=22",
                "PrimaryColour=&H00FFFFFF",
                "OutlineColour=&H00000000",
                "BorderStyle=1",
                "Outline=1.4",
                "Shadow=0",
                "Alignment=2",
                "MarginV=32",
            ]
        )
    # default
    return subtitle_style_preset("boxed", aspect=aspect)


def subtitle_force_style(preset_key: str, overrides: dict | None = None, *, aspect: str = "landscape") -> str:
    # Build an ASS force_style string for ffmpeg subtitles filter.
    # Start from preset and apply optional overrides.
    # Supported overrides:
    # - font_name: str
    # - font_size: int
    # - position: "top"|"center"|"bottom"
    # - outline: float
    # - boxed: bool (if false, use clean style)
    # - margin_v: int
    # - aspect: kept for compatibility; output is landscape-only
    ov = overrides or {}
    key = preset_key
    if isinstance(ov.get("boxed"), bool):
        key = "boxed" if ov.get("boxed") else "clean"

    base = subtitle_style_preset(str(key or "boxed"), aspect=aspect)
    # Parse the preset into a dict.
    style: dict[str, str] = {}
    for part in (base or "").split(","):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        style[k.strip()] = v.strip()

    font_name = ov.get("font_name")
    if isinstance(font_name, str) and font_name.strip():
        style["Fontname"] = font_name.strip()

    font_size = ov.get("font_size")
    try:
        if font_size is not None:
            fs = int(font_size)
            if 16 <= fs <= 120:
                style["Fontsize"] = str(fs)
    except Exception:
        pass

    outline = ov.get("outline")
    try:
        if outline is not None:
            ol = float(outline)
            if 0.0 <= ol <= 10.0:
                style["Outline"] = str(ol)
    except Exception:
        pass

    # Position uses ASS Alignment.
    pos = ov.get("position")
    if isinstance(pos, str):
        p = pos.strip().lower()
        if p == "top":
            style["Alignment"] = "8"  # top-center
        elif p == "center":
            style["Alignment"] = "5"  # middle-center
        elif p == "bottom":
            style["Alignment"] = "2"  # bottom-center

    margin_v = ov.get("margin_v")
    if margin_v is None and isinstance(pos, str):
        p = pos.strip().lower()
        if p == "top":
            margin_v = 60
        elif p == "center":
            margin_v = 28
        elif p == "bottom":
            margin_v = 40
    try:
        if margin_v is not None:
            mv = int(margin_v)
            if 0 <= mv <= 400:
                style["MarginV"] = str(mv)
    except Exception:
        pass

    # Stable order for readability.
    order = [
        "Fontname",
        "Fontsize",
        "PrimaryColour",
        "OutlineColour",
        "BackColour",
        "BorderStyle",
        "Outline",
        "Shadow",
        "Alignment",
        "MarginV",
    ]
    parts: list[str] = []
    for k in order:
        if k in style:
            parts.append(f"{k}={style[k]}")
    for k in sorted(style.keys()):
        if k in order:
            continue
        parts.append(f"{k}={style[k]}")
    return ",".join(parts)


def normalize_subtitle_settings(style: str, cfg: dict | None = None) -> tuple[str, dict]:
    """Resolve subtitle style/overrides into one canonical movie-like shape.

    Policy:
    - Always normalize to a bottom subtitle layout.
    - 1080p Chinese subtitle size target is 20-24 (default 22), and scaled by height.
    """

    raw = cfg if isinstance(cfg, dict) else {}
    out: dict = {}
    s = str(style or "boxed").strip().lower() or "boxed"
    if s not in ("boxed", "clean"):
        s = "boxed"

    # Height-aware safe ranges.
    h = 1080
    try:
        hv = int(raw.get("height") or 1080)
        if 360 <= hv <= 4320:
            h = hv
    except Exception:
        h = 1080

    min_fs = max(16, int(round(h * (20.0 / 1080.0))))
    max_fs = max(min_fs, int(round(h * (24.0 / 1080.0))))
    default_fs = max(min_fs, min(max_fs, int(round(h * (22.0 / 1080.0)))))
    min_mv = max(16, int(round(h * (24.0 / 1080.0))))
    max_mv = max(min_mv, int(round(h * (56.0 / 1080.0))))
    default_mv = max(min_mv, min(max_mv, int(round(h * (32.0 / 1080.0)))))

    if str(raw.get("font_name", "") or "").strip():
        out["font_name"] = str(raw.get("font_name")).strip()
    if raw.get("font_size") is not None:
        try:
            out["font_size"] = int(raw.get("font_size"))
        except Exception:
            pass
    if str(raw.get("position", "") or "").strip():
        out["position"] = str(raw.get("position")).strip().lower()
    if raw.get("outline") is not None:
        try:
            out["outline"] = float(raw.get("outline"))
        except Exception:
            pass
    if raw.get("margin_v") is not None:
        try:
            out["margin_v"] = int(raw.get("margin_v"))
        except Exception:
            pass
    if raw.get("boxed") is not None:
        out["boxed"] = bool(raw.get("boxed"))

    # Canonical safe normalization for boxed/clean.
    out["position"] = "bottom"
    try:
        fs = int(out.get("font_size") or default_fs)
    except Exception:
        fs = default_fs
    out["font_size"] = max(min_fs, min(max_fs, fs))

    try:
        mv = int(out.get("margin_v") or default_mv)
    except Exception:
        mv = default_mv
    out["margin_v"] = max(min_mv, min(max_mv, mv))

    try:
        ol = float(out.get("outline") or 1.4)
    except Exception:
        ol = 1.4
    out["outline"] = max(1.0, min(2.2, ol))

    out["boxed"] = bool(s == "boxed")

    return s, out


def _fmt_ass_time(t: float) -> str:
    # ASS time: H:MM:SS.cc (centiseconds)
    t = max(0.0, float(t or 0.0))
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    cs = int(round((t - int(t)) * 100.0))
    if cs >= 100:
        cs = 99
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _semantic_caption_units(text: str) -> list[str]:
    txt = clean_tts_text(text)
    txt = txt.replace("\r", " ").replace("\n", " ")
    txt = re.sub(r"\s+", " ", txt).strip()
    if not txt:
        return []

    parts = [x.strip() for x in re.split(r"(?<=[，；：。！？,!?])\s*", txt) if x.strip()]
    if not parts:
        return [txt]

    def should_join(prev: str, cur: str) -> bool:
        p = (prev or "").strip()
        c = (cur or "").strip()
        if not p or not c:
            return False
        if re.search(r"(不是|因为|如果|直到|虽然|哪怕|即使|你以为|表面上)$", p):
            return True
        if re.match(r"^(而是|所以|但是|不过|可是|其实|才|就|却|反而|后来|原来|结果|于是)", c):
            return True
        if re.search(r"(不是.+而是|因为.+所以|如果.+就|直到.+才|虽然.+但是|你以为.+其实)", p + c):
            return True
        return False

    units: list[str] = []
    buf = ""
    for part in parts:
        if not buf:
            buf = part
            continue
        if should_join(buf, part):
            buf += part
        else:
            units.append(buf)
            buf = part
    if buf:
        units.append(buf)
    return units


def _split_long_unit(unit: str, *, max_len: int) -> list[str]:
    t = (unit or "").strip()
    if not t:
        return []
    out: list[str] = []
    while len(t) > max_len + 8:
        cut = -1
        for needle in ("，", "；", "：", "。", "！", "？", ",", "!", "?", "结果", "可是", "后来", "原来", "问题是", "所以", "其实", "但是", "如果", "因为"):
            i = t.find(needle)
            if 6 <= i <= max_len + 4:
                cut = i + (1 if len(needle) == 1 else 0)
                break
        if cut < 0:
            cut = max_len
        out.append(t[:cut].strip())
        t = t[cut:].strip()
    if t:
        out.append(t)
    return out


def _tv_single_line(text: str, *, max_chars: int = 24) -> str:
    # Flatten whitespace/newlines and keep it single-line.
    t = clean_subtitle_display_text(text)
    t = t.replace("\r", " ").replace("\n", " ")
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return ""
    if len(t) <= max_chars:
        return t
    # Prefer a natural cut near discourse markers, not a raw hard cut.
    for needle in ("结果", "可是", "后来", "原来", "问题是", "所以", "其实", "只是", "但是", "直到"):
        i = t.find(needle)
        if 4 <= i <= max_chars:
            return t[:i].rstrip("，。！？；： ")
    if max_chars >= 2:
        return t[:max_chars].rstrip()
    return t[:max_chars]


def caption_pages(text: str, *, max_len: int = 24, complexity: float = 1.0) -> list[str]:
    """Generate caption pages with single-line-first behavior."""
    adj_max_len = int(max_len * (1.0 / max(0.7, complexity)))
    adj_max_len = max(18, min(32, adj_max_len))
    
    units0 = _semantic_caption_units(text)
    if not units0:
        return []
    units: list[str] = []
    for unit in units0:
        units.extend(_split_long_unit(unit, max_len=adj_max_len))

    pages = [_tv_single_line(unit, max_chars=adj_max_len) for unit in units]
    return [p for p in pages if p.strip()]
def naive_srt_from_lines(text: str, *, total_duration: float) -> str:
    # Fallback when user uploads voice without timed word boundaries.
    lines = [clean_subtitle_display_text(ln) for ln in (text or "").splitlines() if clean_subtitle_display_text(ln)]
    if not lines:
        return ""
    total_duration = max(1.0, float(total_duration or 0.0))
    per = total_duration / len(lines)

    def fmt(t: float) -> str:
        t = max(0.0, t)
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        ms = int((t - int(t)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    out: list[str] = []
    cur = 0.0
    idx = 0
    for ln in lines:
        pages = caption_pages(ln, max_len=24)
        if not pages:
            cur += per
            continue
        seg_span = per / max(1, len(pages))
        for j, page in enumerate(pages):
            start = cur + (j * seg_span)
            end = cur + ((j + 1) * seg_span)
            idx += 1
            out.append(str(idx))
            out.append(f"{fmt(start)} --> {fmt(end)}")
            out.append(page)
            out.append("")
        cur += per
    return "\n".join(out).strip() + "\n"


def naive_srt_from_scenes(narrations: list[str], durations: list[float]) -> str:
    """Build a simple SRT that aligns captions to shot boundaries.

    This is a stable fallback for MIX: subtitles change when shots change.
    """

    if not narrations or not durations:
        return ""
    n = min(len(narrations), len(durations))
    narrations = narrations[:n]
    durations = [max(0.2, float(d or 0.0)) for d in durations[:n]]

    def fmt(t: float) -> str:
        t = max(0.0, float(t))
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        ms = int((t - int(t)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    out: list[str] = []
    cur = 0.0
    idx = 0
    for i in range(n):
        pages = caption_pages(clean_tts_text(narrations[i]), max_len=24)
        if not pages:
            cur += durations[i]
            continue
        total_span = max(0.4, durations[i])
        seg_span = total_span / max(1, len(pages))
        for j, txt in enumerate(pages):
            start = cur + (j * seg_span)
            end = cur + ((j + 1) * seg_span) - 0.03
            if j == len(pages) - 1:
                end = cur + total_span - 0.03
            if end <= start:
                end = start + max(0.2, seg_span)
            idx += 1
            out.append(str(idx))
            out.append(f"{fmt(start)} --> {fmt(end)}")
            out.append(txt)
            out.append("")
        cur += durations[i]

    return "\n".join(out).strip() + "\n"
