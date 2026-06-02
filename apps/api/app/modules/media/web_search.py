
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List
import hashlib
import json
import os
import time
from pathlib import Path
import concurrent.futures
from urllib.parse import urlparse

import requests

from app.modules.media.wikimedia import WikimediaItem, search_commons
from app.http_client import new_session
from app.settings import settings


# 缓存配置
CACHE_DIR = settings.data_dir / "media_cache"
CACHE_EXPIRY_SECONDS = 3600  # 1小时

CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _get_cache_key(provider: str, kind: str, query: str, aspect: str) -> str:
    """生成缓存键"""
    raw = "|".join([str(provider or ""), str(kind or ""), str(aspect or ""), str(query or "")])
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    safe_aspect = str(aspect or "").replace(" ", "_").replace("/", "_").lower()
    return f"{provider}_{kind}_{safe_aspect}_{digest}".lower()


def provider_aspect_orientation(provider: str, aspect: str) -> str:
    """把项目画幅转换成素材源 API 支持的方向参数。"""
    raw = str(aspect or "").strip().lower()
    if raw in ("portrait", "vertical", "9:16", "0.5625"):
        normalized = "portrait"
    elif raw in ("square", "1:1", "1.0", "1"):
        normalized = "square"
    elif raw in ("landscape", "horizontal", "16:9", "1.7777777777777777"):
        normalized = "landscape"
    else:
        try:
            ratio = float(raw)
        except Exception:
            ratio = 16.0 / 9.0
        if ratio <= 0:
            normalized = "landscape"
        elif 0.82 <= ratio <= 1.22:
            normalized = "square"
        elif ratio < 1.0:
            normalized = "portrait"
        else:
            normalized = "landscape"

    if str(provider or "").strip().lower() == "pixabay":
        if normalized == "portrait":
            return "vertical"
        if normalized == "square":
            return "all"
        return "horizontal"
    return normalized


def readable_title_from_url(page_url: str, fallback: str = "") -> str:
    path = urlparse(str(page_url or "")).path.strip("/")
    slug = path.split("/")[-1] if path else ""
    if not slug:
        return str(fallback or "").strip()
    parts = [part for part in slug.replace("_", "-").split("-") if part]
    while parts and parts[-1].isdigit():
        parts.pop()
    title = " ".join(parts).strip()
    return title or str(fallback or "").strip()


def _get_cache_path(key: str) -> Path:
    """获取缓存文件路径"""
    return CACHE_DIR / f"{key}.json"


def _load_from_cache(key: str) -> Optional[List[dict]]:
    """从缓存加载数据"""
    cache_path = _get_cache_path(key)
    if not cache_path.exists():
        return None
    
    # 检查缓存是否过期
    if time.time() - cache_path.stat().st_mtime > CACHE_EXPIRY_SECONDS:
        return None
    
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except Exception:
        return None


def _save_to_cache(key: str, data: List[dict]) -> None:
    """保存数据到缓存"""
    try:
        cache_path = _get_cache_path(key)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _web_item_to_dict(item: WebMediaItem) -> dict:
    """将WebMediaItem转换为字典"""
    return {
        "provider": item.provider,
        "kind": item.kind,
        "title": item.title,
        "page_url": item.page_url,
        "file_url": item.file_url,
        "thumb_url": item.thumb_url,
        "preview_url": item.preview_url,
        "mime": item.mime,
        "width": item.width,
        "height": item.height,
        "duration_sec": item.duration_sec,
        "license_short": item.license_short,
        "license_url": item.license_url,
        "author": item.author,
        "attribution": item.attribution
    }


def _dict_to_web_item(data: dict) -> WebMediaItem:
    """将字典转换为WebMediaItem"""
    return WebMediaItem(
        provider=data.get("provider", ""),
        kind=data.get("kind", ""),
        title=data.get("title", ""),
        page_url=data.get("page_url", ""),
        file_url=data.get("file_url", ""),
        thumb_url=data.get("thumb_url"),
        preview_url=data.get("preview_url"),
        mime=data.get("mime", ""),
        width=data.get("width"),
        height=data.get("height"),
        duration_sec=data.get("duration_sec"),
        license_short=data.get("license_short", ""),
        license_url=data.get("license_url"),
        author=data.get("author", ""),
        attribution=data.get("attribution", "")
    )


def _to_int(v) -> Optional[int]:
    try:
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


def _to_float(v) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


@dataclass(frozen=True)
class WebMediaItem:
    provider: str
    kind: str  # image|video|audio
    title: str
    page_url: str
    file_url: str
    thumb_url: Optional[str] = None
    preview_url: Optional[str] = None
    mime: str = ""
    width: Optional[int] = None
    height: Optional[int] = None
    duration_sec: Optional[float] = None
    license_short: str = ""
    license_url: Optional[str] = None
    author: str = ""
    attribution: str = ""


def supported_providers() -> tuple[str, ...]:
    # wikimedia requires no API key; others do.
    return ("wikimedia", "pexels", "pixabay")


def provider_supported_kinds(provider: str) -> tuple[str, ...]:
    p = str(provider or "").strip().lower()
    if p == "wikimedia":
        return ("image", "video", "audio")
    if p in ("pexels", "pixabay"):
        # Keep explicit to prevent accidental audio->image fallback.
        return ("image", "video")
    return ()


def provider_supports_kind(provider: str, kind: str) -> bool:
    p = str(provider or "").strip().lower()
    k = str(kind or "").strip().lower()
    return k in provider_supported_kinds(p)


def _to_web_item_wikimedia(kind: str, it: WikimediaItem) -> WebMediaItem:
    return WebMediaItem(
        provider="wikimedia",
        kind=kind,
        title=it.title,
        page_url=it.page_url,
        file_url=it.file_url,
        thumb_url=it.thumb_url,
        preview_url=it.preview_url,
        mime=it.mime,
        width=it.width,
        height=it.height,
        duration_sec=it.duration_sec,
        license_short=it.license_short,
        license_url=it.license_url,
        author=it.author,
        attribution=it.attribution,
    )


def search_web_media(*, provider: str, kind: str, query: str, limit: int, api_key: str = "", timeout_s: int = 30, aspect: str = "landscape") -> list[WebMediaItem]:
    provider = (provider or "wikimedia").strip().lower()
    kind = (kind or "image").strip().lower()
    query = (query or "").strip()
    limit = max(1, min(50, _to_int(limit) or 24))
    if provider not in supported_providers():
        raise ValueError(f"unsupported provider: {provider}")
    if kind not in ("image", "video", "audio"):
        raise ValueError(f"unsupported kind: {kind}")
    if not provider_supports_kind(provider, kind):
        raise ValueError(f"{provider} 不支持 {kind} 搜索")
    if not query:
        return []

    # 生成缓存键
    cache_key = _get_cache_key(provider, kind, query, aspect)
    
    # 尝试从缓存加载
    cached_data = _load_from_cache(cache_key)
    if cached_data:
        # 从缓存数据创建WebMediaItem对象
        items = [_dict_to_web_item(item_data) for item_data in cached_data]
        return items[:limit]

    # 缓存不存在，执行搜索
    items = []
    if provider == "wikimedia":
        wiki_items = search_commons(query=query, kind=kind, limit=limit, timeout_s=max(5, int(timeout_s or 30)))
        items = [_to_web_item_wikimedia(kind, it) for it in wiki_items]
    else:
        if not api_key.strip():
            raise ValueError(f"missing api key for provider: {provider}")

        # 添加重试机制
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                if provider == "pexels":
                    items = _search_pexels(kind=kind, query=query, limit=limit, api_key=api_key, timeout_s=max(5, int(timeout_s or 30)), aspect=aspect)
                    break
                if provider == "pixabay":
                    items = _search_pixabay(kind=kind, query=query, limit=limit, api_key=api_key, timeout_s=max(5, int(timeout_s or 30)), aspect=aspect)
                    break
            except Exception as e:
                if attempt == max_retries:
                    raise
                # 等待一段时间后重试
                time.sleep(1)

    # 只缓存成功的结果（非空）
    if items:
        cache_data = [_web_item_to_dict(item) for item in items]
        _save_to_cache(cache_key, cache_data)
    # 失败结果不缓存，避免缓存污染

    return items


def search_web_media_parallel(
    *,
    kinds: list[str],
    query: str,
    limit: int,
    provider_keys: dict[str, str] | None = None,
    timeout_s: int = 30,
    aspect: str = "landscape",
    provider_failure_cb=None,
) -> list[WebMediaItem]:
    """并行搜索多个素材源和类型
    
    Args:
        kinds: 要搜索的类型列表，如 ["image", "video"]
        query: 搜索查询
        limit: 每个源返回的结果数量
        provider_keys: provider -> api key 映射
        timeout_s: 超时时间
        aspect: 宽高比
    
    Returns:
        合并后的素材列表
    """
    query = (query or "").strip()
    if not query:
        return []
    
    # 要搜索的提供商和类型组合
    search_tasks = []
    
    # 添加 Wikimedia 搜索任务
    for kind in kinds:
        if provider_supports_kind("wikimedia", kind):
            search_tasks.append(("wikimedia", kind, query, limit, "", timeout_s, aspect))
    
    keys = dict(provider_keys or {})
    for provider in ["pexels", "pixabay"]:
        provider_key = str(keys.get(provider) or "").strip()
        if not provider_key:
            continue
        for kind in kinds:
            if provider_supports_kind(provider, kind):
                search_tasks.append((provider, kind, query, limit, provider_key, timeout_s, aspect))
    
    # 并行执行搜索
    all_items = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # 提交所有搜索任务
        future_to_search = {}
        for task in search_tasks:
            provider, kind, q, lim, key, timeout, asp = task
            future = executor.submit(
                search_web_media,
                provider=provider,
                kind=kind,
                query=q,
                limit=lim,
                api_key=key,
                timeout_s=timeout,
                aspect=asp
            )
            future_to_search[future] = (provider, kind)
        
        # 收集搜索结果
        for future in concurrent.futures.as_completed(future_to_search):
            provider, kind = future_to_search[future]
            try:
                items = future.result()
                all_items.extend(items)
            except Exception as exc:
                if callable(provider_failure_cb):
                    try:
                        provider_failure_cb(provider, str(exc), kind, query)
                    except TypeError:
                        provider_failure_cb(provider, str(exc))
                    except Exception:
                        pass
                pass
    
    # 去重：基于file_url
    seen_urls = set()
    unique_items = []
    for item in all_items:
        if item.file_url not in seen_urls:
            seen_urls.add(item.file_url)
            unique_items.append(item)
    
    # 按相关性排序（简单的评分机制）
    def score_item(item: WebMediaItem) -> float:
        score = 0.0
        # 优先选择高分辨率
        if item.width and item.height:
            score += (item.width * item.height) / 1000000
        # 优先选择视频
        if item.kind == "video":
            score += 10.0
        return score
    
    sorted_items = sorted(unique_items, key=score_item, reverse=True)
    
    return sorted_items[:limit * 2]  # 返回更多结果以供选择


def _search_pexels(*, kind: str, query: str, limit: int, api_key: str, timeout_s: int, aspect: str) -> list[WebMediaItem]:
    s = new_session(headers={"Authorization": api_key.strip()})
    orientation = provider_aspect_orientation("pexels", aspect)

    out: list[WebMediaItem] = []
    if kind == "video":
        url = "https://api.pexels.com/videos/search"
        per_page = min(80, max(1, _to_int(limit) or 24))
        params = {"query": query, "per_page": per_page, "orientation": orientation}
        r = s.get(url, params=params, timeout=max(5, int(timeout_s or 30)))
        if not r.ok:
            raise RuntimeError(f"pexels video search failed: {r.status_code}")
        data = r.json() or {}
        for v in data.get("videos") or []:
            try:
                page_url = str(v.get("url") or "").strip()
                image = str(v.get("image") or "").strip() or None
                duration = v.get("duration")
                width = v.get("width")
                height = v.get("height")

                # Choose a reasonable mp4 file (prefer target orientation + larger width)
                best = None
                best_score = -1
                for f in v.get("video_files") or []:
                    link = str(f.get("link") or "").strip()
                    if not link:
                        continue
                    if str(f.get("file_type") or "").lower() != "video/mp4":
                        continue
                    fw = _to_int(f.get("width")) or 0
                    fh = _to_int(f.get("height")) or 0
                    score = fw
                    if fh and fw and fw >= fh:
                        score += 2000
                    if score > best_score:
                        best_score = score
                        best = f

                file_url = str((best or {}).get("link") or "").strip()
                if not file_url:
                    continue

                user = v.get("user") or {}
                author = str(user.get("name") or "").strip()

                out.append(
                    WebMediaItem(
                        provider="pexels",
                        kind="video",
                        title=readable_title_from_url(page_url, str(v.get("id") or "") or query),
                        page_url=page_url or file_url,
                        file_url=file_url,
                        thumb_url=image,
                        preview_url=image,
                        mime="video/mp4",
                        width=_to_int(width),
                        height=_to_int(height),
                        duration_sec=_to_float(duration),
                        license_short="Pexels License",
                        license_url="https://www.pexels.com/license/",
                        author=author,
                        attribution=(page_url or file_url),
                    )
                )
            except Exception:
                continue
        return out[:limit]

    # images
    url = "https://api.pexels.com/v1/search"
    per_page = min(80, max(1, _to_int(limit) or 24))
    params = {"query": query, "per_page": per_page, "orientation": orientation}
    r = s.get(url, params=params, timeout=max(5, int(timeout_s or 30)))
    if not r.ok:
        raise RuntimeError(f"pexels image search failed: {r.status_code}")
    data = r.json() or {}
    for p in data.get("photos") or []:
        try:
            src = p.get("src") or {}
            file_url = str(src.get("large2x") or src.get("large") or src.get("original") or "").strip()
            if not file_url:
                continue
            thumb = str(src.get("tiny") or src.get("small") or "").strip() or None
            preview = str(src.get("medium") or src.get("small") or thumb or "").strip() or None

            page_url = str(p.get("url") or "").strip() or file_url
            author = str(p.get("photographer") or "").strip()

            out.append(
                WebMediaItem(
                    provider="pexels",
                    kind="image",
                    title=str(p.get("alt") or "").strip() or query,
                    page_url=page_url,
                    file_url=file_url,
                    thumb_url=thumb,
                    preview_url=preview,
                    mime="image/jpeg",
                    width=_to_int(p.get("width")),
                    height=_to_int(p.get("height")),
                    license_short="Pexels License",
                    license_url="https://www.pexels.com/license/",
                    author=author,
                    attribution=(page_url or file_url),
                )
            )
        except Exception:
            continue
    return out[:limit]


def score_emotion_media(item: WebMediaItem, *, narration: str = "") -> float:
    """Score emotion-related media items for quality and relevance.
    
    Higher score = better match for emotion content.
    """
    score = 0.0
    
    # Resolution scoring
    if item.width and item.height:
        if item.width >= item.height:
            score += 10.0
        if item.width >= 1080 or item.height >= 1080:  # HD quality
            score += 8.0
        elif item.width >= 720 or item.height >= 720:
            score += 4.0
    
    # Duration scoring (for videos)
    if item.duration_sec:
        if 3.0 <= item.duration_sec <= 15.0:  # Ideal for emotion content
            score += 6.0
        elif 2.0 <= item.duration_sec <= 20.0:
            score += 3.0
    
    # Title relevance scoring
    title = str(item.title or "").lower()
    emotion_terms = [
        "emotion", "feeling", "love", "sad", "happy", "relationship",
        "couple", "alone", "lonely", "together", "family", "person",
        "woman", "man", "close up", "face", "expression", "eyes",
        "silence", "quiet", "moment", "intimate", "tender", "warm"
    ]
    for term in emotion_terms:
        if term in title:
            score += 3.0
            break
    
    # Avoid irrelevant content
    bad_terms = ["logo", "watermark", "text", "template", "icon", "vector", "illustration"]
    for term in bad_terms:
        if term in title:
            score -= 10.0
            break
    
    # Narration relevance scoring
    if narration:
        nar_lower = narration.lower()
        # Check if media matches narration context
        if any(word in nar_lower for word in ["失望", "委屈", "难过"]):
            if any(word in title for word in ["sad", "lonely", "alone", "cry"]):
                score += 5.0
        if any(word in nar_lower for word in ["温暖", "理解", "拥抱"]):
            if any(word in title for word in ["warm", "together", "embrace", "happy"]):
                score += 5.0
        if any(word in nar_lower for word in ["沉默", "距离", "边界"]):
            if any(word in title for word in ["silence", "distance", "alone", "quiet"]):
                score += 5.0
    
    return max(0.0, score)


def _search_pixabay(*, kind: str, query: str, limit: int, api_key: str, timeout_s: int, aspect: str) -> list[WebMediaItem]:
    s = new_session()
    out: list[WebMediaItem] = []
    orientation = provider_aspect_orientation("pixabay", aspect)

    if kind == "video":
        url = "https://pixabay.com/api/videos/"
        per_page = min(200, max(3, _to_int(limit) or 24))
        params = {
            "key": api_key.strip(),
            "q": query,
            "per_page": per_page,
            "orientation": orientation,
            "safesearch": "true",
        }
        r = s.get(url, params=params, timeout=max(5, int(timeout_s or 30)))
        if not r.ok:
            raise RuntimeError(f"pixabay video search failed: {r.status_code}")
        data = r.json() or {}
        for v in data.get("hits") or []:
            try:
                page_url = str(v.get("pageURL") or "").strip()
                image = str(v.get("picture_id") or "").strip()
                # Pixabay provides preview pictures in different fields
                thumb = str(v.get("userImageURL") or "").strip() or None

                videos = v.get("videos") or {}
                # prefer large > medium > small
                cand = videos.get("large") or videos.get("medium") or videos.get("small") or {}
                file_url = str(cand.get("url") or "").strip()
                if not file_url:
                    continue

                out.append(
                    WebMediaItem(
                        provider="pixabay",
                        kind="video",
                        title=str(v.get("tags") or "").strip() or query,
                        page_url=page_url or file_url,
                        file_url=file_url,
                        thumb_url=thumb,
                        preview_url=thumb,
                        mime="video/mp4",
                        width=_to_int(cand.get("width")),
                        height=_to_int(cand.get("height")),
                        duration_sec=_to_float(v.get("duration")),
                        license_short="Pixabay License",
                        license_url="https://pixabay.com/service/license/",
                        author=str(v.get("user") or "").strip(),
                        attribution=(page_url or file_url),
                    )
                )
            except Exception:
                continue
        return out[:limit]

    # images
    url = "https://pixabay.com/api/"
    per_page = min(200, max(3, _to_int(limit) or 24))
    params = {
        "key": api_key.strip(),
        "q": query,
        "per_page": per_page,
        "image_type": "photo",
        "orientation": orientation,
        "safesearch": "true",
    }
    r = s.get(url, params=params, timeout=max(5, int(timeout_s or 30)))
    if not r.ok:
        raise RuntimeError(f"pixabay image search failed: {r.status_code}")
    data = r.json() or {}
    for p in data.get("hits") or []:
        try:
            file_url = str(p.get("largeImageURL") or p.get("webformatURL") or "").strip()
            if not file_url:
                continue
            thumb = str(p.get("previewURL") or "").strip() or None
            page_url = str(p.get("pageURL") or "").strip() or file_url

            out.append(
                WebMediaItem(
                    provider="pixabay",
                    kind="image",
                    title=str(p.get("tags") or "").strip() or query,
                    page_url=page_url,
                    file_url=file_url,
                    thumb_url=thumb,
                    preview_url=thumb,
                    mime="image/jpeg",
                    width=_to_int(p.get("imageWidth")),
                    height=_to_int(p.get("imageHeight")),
                    license_short="Pixabay License",
                    license_url="https://pixabay.com/service/license/",
                    author=str(p.get("user") or "").strip(),
                    attribution=(page_url or file_url),
                )
            )
        except Exception:
            continue
    return out[:limit]
