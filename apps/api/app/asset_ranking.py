def rank_web_search_items(items: list, *, kind: str, query: str, aspect: str = "landscape") -> list:
    q = str(query or "").strip().lower()
    q_terms = [x for x in q.replace("_", " ").replace("-", " ").split() if x]
    want_landscape = str(aspect or "").strip().lower() == "landscape"

    def _score(it) -> float:
        s = 0.0
        title = str(getattr(it, "title", "") or "").lower()
        author = str(getattr(it, "author", "") or "").lower()
        provider = str(getattr(it, "provider", "") or "").lower()
        page_url = str(getattr(it, "page_url", "") or "").lower()
        preview_url = str(getattr(it, "preview_url", "") or "")
        width = int(getattr(it, "width", 0) or 0)
        height = int(getattr(it, "height", 0) or 0)
        dur = float(getattr(it, "duration_sec", 0.0) or 0.0)
        ratio = (float(height) / float(width)) if width > 0 and height > 0 else 0.0

        if kind == "video":
            if want_landscape:
                if width > height:
                    s += 8.0
                elif height == width:
                    s += 2.0
                if 0.45 <= ratio <= 0.95:
                    s += 3.0
            else:
                if height > width:
                    s += 8.0
                elif height == width:
                    s += 2.0
                if 1.3 <= ratio <= 2.2:
                    s += 3.0
            if width >= 1080 or height >= 1080:
                s += 4.0
            if 4.0 <= dur <= 18.0:
                s += 6.0
            elif 2.5 <= dur <= 25.0:
                s += 3.0
        else:
            if want_landscape:
                if width >= height:
                    s += 7.0
                if 0.45 <= ratio <= 0.95:
                    s += 2.0
            else:
                if height >= width:
                    s += 7.0
                if 1.1 <= ratio <= 2.2:
                    s += 2.0
            if width >= 1000 or height >= 1000:
                s += 4.0

        if preview_url:
            s += 1.0
        if provider == "pexels":
            s += 1.0

        for t in q_terms[:6]:
            if t in title:
                s += 2.0
            if t in page_url:
                s += 0.8

        bad_terms = ("logo", "watermark", "template", "icon", "vector", "avatar", "banner", "poster")
        if any(t in title for t in bad_terms):
            s -= 8.0
        if any(t in page_url for t in bad_terms):
            s -= 5.0
        if any(t in title for t in ("animation", "cartoon", "illustration")) and kind != "image":
            s -= 3.0
        if any(t in author for t in ("official", "stock")):
            s += 0.5
        return s

    try:
        return sorted(items or [], key=_score, reverse=True)
    except Exception:
        return items or []
