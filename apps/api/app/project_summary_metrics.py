import json
import re

from app.models import Project, Scene


def _scene_meta_dict(scene: Scene) -> dict:
    try:
        meta = json.loads(getattr(scene, "meta_json", "{}") or "{}")
        return meta if isinstance(meta, dict) else {}
    except Exception:
        return {}


def scene_render_meta(scene: Scene) -> dict:
    meta = _scene_meta_dict(scene)
    render = meta.get("render") if isinstance(meta.get("render"), dict) else {}
    return render if isinstance(render, dict) else {}


def scene_clip_range(scene: Scene) -> tuple[float | None, float | None]:
    render = scene_render_meta(scene)
    start = render.get("clip_start_sec")
    end = render.get("clip_end_sec")
    try:
        start_f = float(start) if start is not None else None
    except Exception:
        start_f = None
    try:
        end_f = float(end) if end is not None else None
    except Exception:
        end_f = None
    if start_f is None or end_f is None or end_f <= start_f:
        return (None, None)
    return (start_f, end_f)


def clip_overlap_ratio(a: tuple[float | None, float | None], b: tuple[float | None, float | None]) -> float:
    a0, a1 = a
    b0, b1 = b
    if a0 is None or a1 is None or b0 is None or b1 is None:
        return 1.0
    overlap = max(0.0, min(a1, b1) - max(a0, b0))
    if overlap <= 0:
        return 0.0
    shorter = max(1e-6, min(a1 - a0, b1 - b0))
    return max(0.0, min(1.0, overlap / shorter))


def duplicate_scene_asset_ids(scenes: list[Scene], *, overlap_threshold: float = 0.6) -> set[int]:
    if not scenes:
        return set()
    groups: dict[int, list[Scene]] = {}
    for scene in scenes:
        try:
            aid = int(getattr(scene, "image_asset_id", 0) or 0)
        except Exception:
            aid = 0
        if aid <= 0:
            continue
        groups.setdefault(aid, []).append(scene)

    duplicates: set[int] = set()
    for grouped_scenes in groups.values():
        if len(grouped_scenes) <= 1:
            continue
        first_render = scene_render_meta(grouped_scenes[0])
        asset_kind = str(first_render.get("asset_kind") or "").strip().lower()
        if asset_kind and asset_kind != "video":
            duplicates.update(int(getattr(scene, "id", 0) or 0) for scene in grouped_scenes if getattr(scene, "id", None) is not None)
            continue
        if not asset_kind:
            duplicate_all = True
            for scene in grouped_scenes:
                render = scene_render_meta(scene)
                if str(render.get("asset_kind") or "").strip().lower() == "video":
                    duplicate_all = False
                    break
            if duplicate_all:
                duplicates.update(int(getattr(scene, "id", 0) or 0) for scene in grouped_scenes if getattr(scene, "id", None) is not None)
                continue
        ranges = [(scene, scene_clip_range(scene)) for scene in grouped_scenes]
        flagged: set[int] = set()
        for idx in range(len(ranges)):
            left_scene, left_range = ranges[idx]
            left_id = int(getattr(left_scene, "id", 0) or 0)
            if left_id <= 0:
                continue
            for jdx in range(idx + 1, len(ranges)):
                right_scene, right_range = ranges[jdx]
                right_id = int(getattr(right_scene, "id", 0) or 0)
                if right_id <= 0:
                    continue
                if clip_overlap_ratio(left_range, right_range) >= overlap_threshold:
                    flagged.add(left_id)
                    flagged.add(right_id)
        duplicates.update(flagged)
    return duplicates


def subtitle_style_label(style: str) -> str:
    s = str(style or "boxed").strip().lower()
    if s == "boxed":
        return "电影黑底字幕"
    if s == "clean":
        return "纯描边字幕"
    return s or "电影黑底字幕"


def tts_backend_label(backend: str) -> str:
    b = str(backend or "auto").strip().lower()
    if b == "edge":
        return "微软在线 TTS"
    if b == "offline_piper":
        return "离线中文配音（默认）"
    return "自动（优先离线）"


def _slug_words(text: str, *, limit: int = 4) -> str:
    t = str(text or "").strip().lower()
    if not t:
        return ""
    t = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", t)
    parts = [p for p in re.split(r"\s+", t) if p]
    return "_".join(parts[: max(1, int(limit or 4))]) if parts else ""


def summary_continuity_metrics(scenes: list[Scene]) -> dict:
    rows: list[dict] = []
    for sc in scenes:
        meta = _scene_meta_dict(sc)
        visual = meta.get("visual") if isinstance(meta.get("visual"), dict) else {}
        continuity = meta.get("continuity") if isinstance(meta.get("continuity"), dict) else {}
        anchor = str(continuity.get("anchor_id") or visual.get("anchor_id") or "").strip()
        if not anchor:
            anchor = _slug_words(f"{visual.get('anchor_subject') or visual.get('subject') or ''} {visual.get('anchor_setting') or visual.get('setting') or ''}", limit=6)
        rows.append({
            "idx": int(getattr(sc, "idx", 0) or 0),
            "anchor": anchor,
            "jump": bool(continuity.get("jump_from_prev")),
            "subject": _slug_words(str(visual.get("subject") or ""), limit=3),
            "setting": _slug_words(str(visual.get("setting") or ""), limit=3),
            "time": _slug_words(str(visual.get("time") or ""), limit=2),
        })
    rows = [r for r in sorted(rows, key=lambda x: x["idx"]) if int(r.get("idx", 0) or 0) > 0]
    if not rows:
        return {"anchor_coverage": 1.0, "adjacent_jump_rate": 0.0}
    counts: dict[str, int] = {}
    for r in rows:
        a = str(r.get("anchor") or "")
        if a:
            counts[a] = int(counts.get(a, 0)) + 1
    top = max(counts.values()) if counts else 0
    coverage = float(top) / float(max(1, len(rows)))
    jumps = 0
    pairs = max(1, len(rows) - 1)
    for i in range(1, len(rows)):
        if bool(rows[i].get("jump")):
            jumps += 1
            continue
        changed = int(rows[i - 1].get("subject") != rows[i].get("subject")) + int(rows[i - 1].get("setting") != rows[i].get("setting")) + int(rows[i - 1].get("time") != rows[i].get("time"))
        if changed >= 2:
            jumps += 1
    return {"anchor_coverage": round(coverage, 4), "adjacent_jump_rate": round(float(jumps) / float(pairs), 4)}


def summary_main_clip_metrics(scenes: list[Scene]) -> dict:
    total_dur = 0.0
    main_dur = 0.0
    main_scene_count = 0
    main_asset_ids: set[int] = set()
    for sc in scenes:
        dur = max(2.0, float(getattr(sc, "duration_sec", 0.0) or 2.0))
        total_dur += dur
        meta = _scene_meta_dict(sc)
        render = meta.get("render") if isinstance(meta.get("render"), dict) else {}
        role = str(render.get("role") or "").strip().lower()
        if role != "main":
            continue
        main_scene_count += 1
        main_dur += dur
        aid = render.get("main_asset_id")
        try:
            if aid is not None and int(aid) > 0:
                main_asset_ids.add(int(aid))
            elif getattr(sc, "image_asset_id", None):
                main_asset_ids.add(int(sc.image_asset_id or 0))
        except Exception:
            pass
    coverage_pct = int(round((main_dur / max(1e-6, total_dur)) * 100.0)) if total_dur > 0 else 0
    return {"main_clip_count": len(main_asset_ids), "main_scene_count": int(main_scene_count), "main_clip_coverage": max(0, min(100, coverage_pct))}


def content_reasonability_metrics(project: Project, scenes: list[Scene]) -> dict:
    narrations = [str(getattr(s, "narration", "") or "").strip() for s in scenes if str(getattr(s, "narration", "") or "").strip()]
    media_queries = [str(getattr(s, "media_query", "") or "").strip().lower() for s in scenes if str(getattr(s, "media_query", "") or "").strip()]
    if not narrations:
        return {"score": 70, "items": ["旁白为空或过少，语义主线不完整"], "metrics": {"abstract_ratio": 0, "weak_query_ratio": 100, "repetition_ratio": 0, "risk_terms": 0}}
    concrete_re = re.compile(r"(\d|今天|昨天|明天|办公室|会议|地铁|客厅|饭桌|街头|学校|公司|厨房|卧室|手机|电脑|画面|镜头|视频|照片)")
    abstract_re = re.compile(r"(人生|世界|本质|意义|成功|失败|成长|情绪价值|认知|命运|幸福|绝望)")
    risky_re = re.compile(r"(100%|保证|包赚|暴富|稳赚|内幕|博彩|赌博|仇恨|极端)", re.IGNORECASE)
    abstract_count = 0
    risk_hits = 0
    for t in narrations:
        has_concrete = bool(concrete_re.search(t))
        has_abstract = bool(abstract_re.search(t))
        if has_abstract and not has_concrete:
            abstract_count += 1
        risk_hits += len(risky_re.findall(t))
    weak_query_terms = {"scene", "lifestyle scene", "人物", "生活", "场景", "镜头", "画面", "素材", "video"}
    weak_query_count = 0
    for q in media_queries:
        if len(q) < 4 or q in weak_query_terms:
            weak_query_count += 1
    norm_lines = [re.sub(r"\s+", "", x.lower()) for x in narrations]
    unique_lines = len(set(norm_lines))
    repetition_ratio = 0.0 if not norm_lines else max(0.0, 1.0 - (float(unique_lines) / float(len(norm_lines))))
    abstract_ratio = float(abstract_count) / float(max(1, len(narrations)))
    weak_query_ratio = float(weak_query_count) / float(max(1, len(media_queries) or 1))
    score = 100
    score -= int(round(abstract_ratio * 35.0))
    score -= int(round(weak_query_ratio * 30.0))
    score -= int(round(repetition_ratio * 25.0))
    score -= min(20, int(risk_hits) * 4)
    score = max(0, min(100, score))
    items: list[str] = []
    if abstract_ratio > 0.4:
        items.append(f"叙述偏抽象（{int(abstract_ratio * 100)}%），建议补充可视化场景细节")
    if weak_query_ratio > 0.35:
        items.append(f"素材检索词偏泛（{int(weak_query_ratio * 100)}%），建议改成可检索短词")
    if repetition_ratio > 0.3:
        items.append(f"旁白重复度偏高（{int(repetition_ratio * 100)}%），建议压缩重复表达")
    if risk_hits > 0:
        items.append(f"检测到 {int(risk_hits)} 处风险措辞，建议改为中性表述")
    return {
        "score": score,
        "items": items,
        "metrics": {
            "abstract_ratio": max(0, min(100, int(round(abstract_ratio * 100.0)))),
            "weak_query_ratio": max(0, min(100, int(round(weak_query_ratio * 100.0)))),
            "repetition_ratio": max(0, min(100, int(round(repetition_ratio * 100.0)))),
            "risk_terms": max(0, int(risk_hits)),
        },
    }
