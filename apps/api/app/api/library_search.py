from typing import cast

from fastapi import APIRouter, HTTPException

from app.asset_ranking import rank_web_search_items
from app.db import session_scope
from app.modules.media.query_rewrite import rewrite_to_en_stock_keywords
from app.modules.media.service import get_media_api_key
from app.modules.media.web_search import provider_supports_kind, search_web_media, supported_providers
from app.schemas import WebMediaItemOut, WebSearchOut

router = APIRouter(tags=["asset"])


@router.get("/api/library/web-search", response_model=WebSearchOut)
def web_search(query: str, provider: str = "wikimedia", kind: str = "image", limit: int = 24, aspect: str = "landscape"):
    provider = (provider or "wikimedia").strip().lower()
    kind = (kind or "image").strip().lower()
    if provider not in supported_providers():
        raise HTTPException(status_code=400, detail=f"不支持的来源：{provider}")
    if kind not in ("image", "video", "audio"):
        kind = "image"
    if not provider_supports_kind(provider, kind):
        raise HTTPException(status_code=400, detail=f"{provider} 不支持 {kind} 搜索")
    limit = max(1, min(50, int(limit or 24)))
    q = (query or "").strip()
    if not q:
        return WebSearchOut(ok=True, items=[])
    api_key = ""
    if provider in ("pexels", "pixabay"):
        with session_scope() as session:
            api_key = get_media_api_key(session, provider)
        if not api_key.strip():
            raise HTTPException(status_code=400, detail=f"{provider} 未配置 API Key，请到设置中填写")
    q_used = q
    try:
        en_q = rewrite_to_en_stock_keywords(q)
        if en_q:
            q_used = en_q
    except Exception:
        q_used = q
    try:
        items = search_web_media(provider=provider, kind=kind, query=q_used, limit=limit, api_key=api_key, aspect=aspect)
        if (not items) and q_used != q:
            items = search_web_media(provider=provider, kind=kind, query=q, limit=limit, api_key=api_key, aspect=aspect)
        items = rank_web_search_items(items, kind=kind, query=q_used or q, aspect=aspect)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"搜索失败：{exc}")
    out_items: list[WebMediaItemOut] = [
        WebMediaItemOut(
            provider=item.provider,
            kind=item.kind,
            title=item.title,
            page_url=item.page_url,
            file_url=item.file_url,
            thumb_url=item.thumb_url,
            preview_url=item.preview_url,
            mime=item.mime,
            width=item.width,
            height=item.height,
            duration_sec=item.duration_sec,
            license_short=item.license_short,
            license_url=item.license_url,
            author=item.author,
            attribution=item.attribution,
        )
        for item in items
    ]
    return WebSearchOut(ok=True, items=cast(list[WebMediaItemOut], out_items))
