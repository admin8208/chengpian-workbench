"""Media provider router extracted from the main application entrypoint."""

from fastapi import APIRouter, HTTPException

from app.db import session_scope
from app.modules.media.service import get_media_api_key, has_media_api_key, upsert_media_api_key
from app.modules.media.web_search import provider_supported_kinds, provider_supports_kind, search_web_media, supported_providers
from app.schemas import MediaKeyIn, MediaProviderStatusOut, MediaProviderTestIn, MediaProviderTestOut, WebMediaItemOut

router = APIRouter(tags=["media"])


@router.get("/api/media/providers", response_model=list[MediaProviderStatusOut])
def media_providers_status():
    provs = list(supported_providers())
    out: list[MediaProviderStatusOut] = []
    with session_scope() as session:
        for p in provs:
            kinds = list(provider_supported_kinds(p))
            if p == "wikimedia":
                out.append(MediaProviderStatusOut(provider="wikimedia", has_api_key=False, api_key="", ok=True, detail="无需 API Key · 适合历史资料/百科素材；情感、职场、家庭仅建议作为兜底", supported_kinds=kinds))
                continue
            api_key = get_media_api_key(session, p)
            ok = bool(api_key.strip())
            out.append(
                MediaProviderStatusOut(
                    provider=p,
                    has_api_key=ok,
                    api_key=api_key,
                    ok=True,
                    detail=("已配置" if ok else "未配置，素材模式会退回 Wikimedia 兜底，生活类画面质量会受限") + f" · 支持 {','.join(kinds)}",
                    supported_kinds=kinds,
                )
            )
    return out


@router.post("/api/media/providers/{provider}/key")
def set_media_provider_key(provider: str, body: MediaKeyIn):
    provider = (provider or "").strip().lower()
    if provider not in supported_providers():
        raise HTTPException(status_code=404, detail="provider 不存在")
    if provider == "wikimedia":
        return {"ok": True, "note": "Wikimedia 不需要 API Key"}
    with session_scope() as session:
        upsert_media_api_key(session, provider, body.api_key)
    return {"ok": True}


@router.post("/api/media/providers/{provider}/test", response_model=MediaProviderTestOut)
def test_media_provider(provider: str, body: MediaProviderTestIn):
    provider = (provider or "").strip().lower()
    if provider not in supported_providers():
        return MediaProviderTestOut(ok=False, error="provider 不存在")
    kind = (body.kind or "image").strip().lower()
    if not provider_supports_kind(provider, kind):
        return MediaProviderTestOut(ok=False, error=f"{provider} 不支持 {kind} 搜索")
    q = (body.query or "").strip()
    limit = int(body.limit or 5)
    if not q:
        return MediaProviderTestOut(ok=False, error="query 为空")
    try:
        api_key = ""
        if provider in ("pexels", "pixabay"):
            with session_scope() as session:
                api_key = get_media_api_key(session, provider)
            if not api_key:
                return MediaProviderTestOut(ok=False, error="未设置 API Key")
        items = search_web_media(provider=provider, kind=kind, query=q, limit=limit, api_key=api_key, aspect=body.aspect)
        out_items = [
            WebMediaItemOut(
                provider=it.provider,
                kind=it.kind,
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
            for it in items
        ]
        return MediaProviderTestOut(ok=True, items=out_items)
    except Exception as e:
        return MediaProviderTestOut(ok=False, error=str(e))
