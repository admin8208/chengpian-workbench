import re


def _slug_words(text: str, *, limit: int = 4) -> str:
    t = str(text or "").strip().lower()
    if not t:
        return ""
    t = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", t)
    parts = [p for p in re.split(r"\s+", t) if p]
    if not parts:
        return ""
    return "_".join(parts[: max(1, int(limit or 4))])


def _has_transition_cue(text: str) -> bool:
    t = str(text or "").strip().lower()
    if not t:
        return False
    cues = ("后来", "接着", "随后", "转到", "下一秒", "第二天", "当晚", "与此同时", "after", "later", "next", "meanwhile")
    return any(c in t for c in cues)


def scene_anchor_from_visual(visual: dict, *, fallback_text: str = "") -> dict:
    v = visual if isinstance(visual, dict) else {}
    subject = str(v.get("subject") or "").strip()
    setting = str(v.get("setting") or "").strip()
    anchor_type = str(v.get("anchor_type") or "person").strip().lower() or "person"
    raw_anchor = str(v.get("anchor_id") or "").strip()
    if not raw_anchor:
        base = _slug_words(subject, limit=3) or _slug_words(fallback_text, limit=3) or "scene"
        place = _slug_words(setting, limit=2)
        raw_anchor = f"{base}_{place}" if place else base
    anchor_id = _slug_words(raw_anchor, limit=6) or "scene"
    if anchor_type not in ("person", "location", "object"):
        anchor_type = "person"
    return {"anchor_id": anchor_id, "anchor_type": anchor_type, "anchor_subject": subject, "anchor_setting": setting}


def continuity_metrics_from_rows(rows: list[dict]) -> dict:
    if not rows:
        return {"anchor_coverage": 1.0, "adjacent_jump_rate": 0.0, "jump_pairs": [], "dominant_anchor_id": ""}
    anchors: list[str] = []
    for r in rows:
        visual = r.get("visual") if isinstance(r.get("visual"), dict) else {}
        nar = str(r.get("narration") or "")
        anc = scene_anchor_from_visual(visual, fallback_text=nar)
        anchors.append(str(anc.get("anchor_id") or ""))
    counts: dict[str, int] = {}
    for a in anchors:
        counts[a] = int(counts.get(a, 0)) + 1
    dominant = max(counts.items(), key=lambda kv: kv[1])[0] if counts else ""
    coverage = float(counts.get(dominant, 0)) / float(max(1, len(rows)))
    jump_pairs: list[tuple[int, int]] = []
    for i in range(1, len(rows)):
        prev = rows[i - 1]
        cur = rows[i]
        pv = prev.get("visual") if isinstance(prev.get("visual"), dict) else {}
        cv = cur.get("visual") if isinstance(cur.get("visual"), dict) else {}
        changed = (
            int(_slug_words(str(pv.get("subject") or ""), limit=3) != _slug_words(str(cv.get("subject") or ""), limit=3))
            + int(_slug_words(str(pv.get("setting") or ""), limit=3) != _slug_words(str(cv.get("setting") or ""), limit=3))
            + int(_slug_words(str(pv.get("time") or ""), limit=2) != _slug_words(str(cv.get("time") or ""), limit=2))
        )
        if changed >= 2 and not _has_transition_cue(str(cur.get("narration") or "")):
            jump_pairs.append((int(prev.get("idx") or i), int(cur.get("idx") or (i + 1))))
    jump_rate = float(len(jump_pairs)) / float(max(1, len(rows) - 1))
    return {"anchor_coverage": round(coverage, 4), "adjacent_jump_rate": round(jump_rate, 4), "jump_pairs": jump_pairs, "dominant_anchor_id": dominant}
