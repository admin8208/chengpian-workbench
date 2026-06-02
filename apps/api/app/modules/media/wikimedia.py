
import hashlib
import re
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import quote, urlparse

import requests

from app.http_client import new_session


_COMMONS_API = "https://commons.wikimedia.org/w/api.php"


def _strip_html(s: str) -> str:
    # extmetadata often contains HTML.
    s = s or ""
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _norm_license(lic: str) -> str:
    lic = (lic or "").strip().lower()
    lic = lic.replace("creative commons", "cc")
    lic = lic.replace("attribution", "by")
    lic = lic.replace("share alike", "by-sa")
    lic = re.sub(r"\s+", " ", lic)
    return lic


def is_allowed_license(license_short: str) -> bool:
    lic = _norm_license(license_short)
    if not lic:
        return False
    if "public domain" in lic or lic.startswith("pd"):
        return True
    if "cc0" in lic:
        return True
    # allow cc-by and cc-by-sa
    if "cc by-sa" in lic or "cc-by-sa" in lic or "by-sa" in lic:
        return True
    if "cc by" in lic or "cc-by" in lic or re.search(r"\bby\b", lic):
        return True
    return False


def kind_from_mime(mime: str) -> str:
    m = (mime or "").lower()
    if m.startswith("image/"):
        return "image"
    if m.startswith("video/"):
        return "video"
    if m.startswith("audio/"):
        return "audio"
    return "other"


def _safe_int(v: Any) -> Optional[int]:
    try:
        return int(v)
    except Exception:
        return None


def _safe_float(v: Any) -> Optional[float]:
    try:
        return float(v)
    except Exception:
        return None


def url_hash(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    # drop query for stable hashing
    p = urlparse(u)
    base = f"{p.scheme}://{p.netloc}{p.path}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class WikimediaItem:
    title: str
    page_url: str
    file_url: str
    thumb_url: Optional[str]
    preview_url: Optional[str]
    mime: str
    width: Optional[int]
    height: Optional[int]
    duration_sec: Optional[float]
    license_short: str
    license_url: Optional[str]
    author: str
    attribution: str


def search_commons(*, query: str, kind: str, limit: int = 24, timeout_s: int = 20) -> list[WikimediaItem]:
    q = (query or "").strip()
    if not q:
        return []
    kind = (kind or "image").strip().lower()
    if kind not in ("image", "video", "audio"):
        kind = "image"

    # Search File: namespace (6)
    # Use generator=search + imageinfo for URLs + extmetadata for license/author
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": 6,
        "gsrlimit": max(1, min(50, int(limit or 24))),
        "gsrsearch": q,
        "prop": "imageinfo",
        "iiprop": "url|mime|size|extmetadata",
        "iiurlwidth": 512,
        "origin": "*",
    }

    s = new_session(headers={"Accept": "application/json"})
    r = s.get(_COMMONS_API, params=params, timeout=timeout_s)
    if r.status_code == 403:
        raise RuntimeError("Wikimedia Commons API returned 403 (access denied)")
    r.raise_for_status()
    data = r.json() or {}

    pages = (((data.get("query") or {}).get("pages")) or {})
    out: list[WikimediaItem] = []
    for _, page in pages.items():
        title = str(page.get("title") or "").strip()
        # pageid etc not needed
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        ii = infos[0] or {}
        mime = str(ii.get("mime") or "").strip().lower()
        file_url = str(ii.get("url") or "").strip()
        thumb_url = ii.get("thumburl")
        # For many file types, thumburl is adequate preview. Keep preview_url as thumb.
        preview_url = thumb_url

        if not file_url:
            continue

        # Filter by kind and supported mime types
        if kind == "image":
            if not mime.startswith("image/"):
                continue
            # Avoid SVG/TIFF for MVP; keep raster images
            if mime in ("image/svg+xml", "image/tiff"):
                continue
            # Keep only common raster formats we can serve/render easily.
            if mime not in ("image/jpeg", "image/png", "image/webp"):
                continue
        elif kind == "video":
            if not mime.startswith("video/"):
                continue
        elif kind == "audio":
            if not mime.startswith("audio/"):
                continue

        extmeta = (ii.get("extmetadata") or {})
        lic = _strip_html(str((extmeta.get("LicenseShortName") or {}).get("value") or ""))
        lic_url = str((extmeta.get("LicenseUrl") or {}).get("value") or "").strip() or None
        author = _strip_html(str((extmeta.get("Artist") or {}).get("value") or ""))

        if not is_allowed_license(lic):
            continue

        # Duration is not always present; some video files provide "duration".
        duration = _safe_float(ii.get("duration"))
        width = _safe_int(ii.get("width"))
        height = _safe_int(ii.get("height"))

        # Example: File:Foo bar.jpg -> https://commons.wikimedia.org/wiki/File:Foo_bar.jpg
        safe_title = title.replace(" ", "_")
        page_url = "https://commons.wikimedia.org/wiki/" + quote(safe_title, safe=":/_")

        # Build attribution text (simple)
        parts = []
        if title:
            parts.append(title)
        if author:
            parts.append(f"by {author}")
        if lic:
            parts.append(lic)
        parts.append(page_url)
        attribution = " | ".join([p for p in parts if p])

        out.append(
            WikimediaItem(
                title=title,
                page_url=page_url,
                file_url=file_url,
                thumb_url=str(thumb_url) if thumb_url else None,
                preview_url=str(preview_url) if preview_url else None,
                mime=mime,
                width=width,
                height=height,
                duration_sec=duration,
                license_short=lic,
                license_url=lic_url,
                author=author,
                attribution=attribution,
            )
        )

    # keep stable order: results are already limited
    return out[: max(0, int(limit or 24))]
