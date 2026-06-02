"""Image provider router extracted from the main application entrypoint."""

import time

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.image_service import get_default_image_provider, get_image_api_key, has_image_api_key, normalize_image_providers, set_default_image_provider, upsert_image_api_key, upsert_provider
from app.llm_client import normalize_provider_base_url, openai_compat_generate_image, openai_compat_list_models
from app.tasks_image_provider import image_generate_timeout_s
from app.db import session_scope
from app.models import ImageProvider
from app.schemas import ImageKeyIn, ImageProviderIn, ImageProviderOut, ImageStatusOut, ImageTestIn, ImageTestOut

router = APIRouter(tags=["image"])


def _is_retryable_image_error(detail: str) -> bool:
    low = str(detail or "").lower()
    return any(token in low for token in ("error 520", "status\":520", " 520", "timeout", "timed out", "502", "503", "504"))


def _format_image_test_error(detail: str) -> str:
    raw = str(detail or "").strip()
    low = raw.lower()
    if "request timeout" in low or "timed out" in low or "timeout" in low:
        return (
            "测试生图超时：已连通服务端，但 `images/generations` 长时间无响应。"
            "这通常表示当前中转暂不支持生图、当前模型不可用，或上游服务拥堵。"
            f"原始错误：{raw}"
        )
    if _is_retryable_image_error(raw):
        return f"上游生图服务暂时不稳定，请稍后重试。原始错误：{raw}"
    return raw or "测试失败"


def _image_test_failure_message(detail: str) -> str:
    raw = str(detail or "").strip()
    low = raw.lower()
    if "api key" in low or "鉴权" in raw or "unauthorized" in low or "401" in low:
        return "测试失败：生图模型鉴权失败（401），请检查 API Key。"
    if "403" in low or "forbidden" in low or "permission denied" in low or "拒绝访问" in raw:
        return "测试失败：生图模型拒绝访问（403），请检查账号权限、模型权限或风控策略。"
    if "429" in low or "rate limit" in low or "quota" in low:
        return "测试失败：生图模型请求被限流或额度不足（429）。"
    if "不在提供商返回的模型列表" in raw or ("model" in low and ("not" in low or "模型" in raw)):
        return "测试失败：生图模型名不可用，请检查模型名称。"
    if "timeout" in low or "timed out" in low or "超时" in raw:
        return "测试失败：生图模型响应超时，请检查服务地址、模型名或服务商状态。"
    if "没有返回可保存的图片数据" in raw or "unexpected response" in low:
        return "测试失败：生图接口没有返回可保存的图片数据。"
    if "接口地址不能为空" in raw or "base_url" in low:
        return "测试失败：请填写生图服务地址。"
    if "模型名不能为空" in raw:
        return "测试失败：请填写生图模型名。"
    if _is_retryable_image_error(raw):
        return "测试失败：上游生图服务暂时不稳定，请稍后重试。"
    if any(token in low for token in ("502", "503", "504")):
        return "测试失败：生图上游服务异常（5xx），请稍后重试。"
    if raw:
        return f"测试失败：{raw}"
    return "测试失败：生图模型不可用，请检查服务地址、模型名或 API Key。"


def image_provider_to_out(p: ImageProvider, api_key: str = "") -> ImageProviderOut:
    assert p.id is not None
    return ImageProviderOut(
        id=int(p.id),
        name=p.name,
        type=p.type,
        base_url=p.base_url,
        default_model=p.default_model,
        enabled=bool(p.enabled),
        is_default=bool(p.is_default),
        api_key=api_key,
    )


@router.get("/api/image/status", response_model=ImageStatusOut)
def image_status():
    with session_scope() as session:
        p = get_default_image_provider(session)
        if not p or p.id is None:
            return ImageStatusOut(has_default=False)
        return ImageStatusOut(
            has_default=True,
            default_provider_id=int(p.id),
            default_provider_name=p.name,
            default_provider_type=p.type,
            default_model=p.default_model,
            has_api_key=has_image_api_key(session, int(p.id)),
        )


@router.get("/api/image/providers", response_model=list[ImageProviderOut])
def list_image_providers():
    with session_scope() as session:
        normalize_image_providers(session)
        items = sorted(session.exec(select(ImageProvider)).all(), key=lambda item: int(item.id or 0))
        return [image_provider_to_out(p, get_image_api_key(session, int(p.id))) for p in items if p.id is not None]


@router.post("/api/image/providers", response_model=ImageProviderOut)
def create_image_provider(body: ImageProviderIn):
    if body.type not in ("openai_compat",):
        raise HTTPException(status_code=400, detail="type 只能是 openai_compat")
    normalized_base_url = normalize_provider_base_url(body.type, body.base_url)
    with session_scope() as session:
        normalize_image_providers(session)
        p = upsert_provider(
            session,
            name=body.name,
            type_=body.type,
            base_url=normalized_base_url,
            default_model=body.default_model.strip(),
            enabled=bool(body.enabled),
            is_default=bool(body.is_default),
        )
        if body.api_key.strip():
            upsert_image_api_key(session, int(p.id), body.api_key)
        if p.is_default:
            set_default_image_provider(session, int(p.id))
        normalize_image_providers(session)
        session.flush()
        session.refresh(p)
        return image_provider_to_out(p, get_image_api_key(session, int(p.id)))


@router.post("/api/image/providers/{provider_id}/key")
def set_image_key(provider_id: int, body: ImageKeyIn):
    with session_scope() as session:
        p = session.exec(select(ImageProvider).where(ImageProvider.id == provider_id)).first()
        if not p or p.id is None:
            raise HTTPException(status_code=404, detail="provider 不存在")
        upsert_image_api_key(session, int(p.id), body.api_key)
    return {"ok": True}


@router.post("/api/image/test", response_model=ImageTestOut)
def test_image_provider(body: ImageTestIn):
    with session_scope() as session:
        try:
            p = session.exec(select(ImageProvider).where(ImageProvider.id == body.provider_id)).first() if body.provider_id else None
            base_url = normalize_provider_base_url("openai_compat", str((body.base_url or getattr(p, "base_url", "") or "")).strip())
            default_model = str((body.default_model or getattr(p, "default_model", "") or "")).strip()
            if not base_url:
                return ImageTestOut(ok=False, error="接口地址不能为空", message=_image_test_failure_message("接口地址不能为空"))
            if not default_model:
                return ImageTestOut(ok=False, error="模型名不能为空", message=_image_test_failure_message("模型名不能为空"))
            key = str(body.api_key or "").strip() or (get_image_api_key(session, int(p.id)) if p and p.id is not None else "")
            if not key:
                return ImageTestOut(ok=False, error="未设置 API Key", message=_image_test_failure_message("未设置 API Key"))
            models = openai_compat_list_models(base_url=base_url, api_key=key, timeout_s=15)
            if default_model not in models:
                return ImageTestOut(
                    ok=False,
                    error=f"模型 `{default_model}` 不在提供商返回的模型列表中，请检查模型名称或更换提供商。",
                    message=_image_test_failure_message(f"模型 `{default_model}` 不在提供商返回的模型列表中，请检查模型名称或更换提供商。"),
                )
            prompt = (body.prompt or "test image").strip()[:200]
            requested_size = str(body.size or "").strip().lower()
            # 允许设置页按目标尺寸验证，避免测试通过但真实项目尺寸不可用。
            size = requested_size if requested_size in {"1024x1024", "1664x944", "944x1664"} else "1024x1024"
            timeout_s = image_generate_timeout_s()
            obj = None
            last_error = ""
            for idx in range(3):
                try:
                    obj = openai_compat_generate_image(
                        base_url=base_url,
                        api_key=key,
                        model=default_model,
                        prompt=prompt,
                        size=size,
                        timeout_s=timeout_s,
                    )
                    break
                except Exception as e:
                    last_error = str(e)
                    if idx >= 2 or not _is_retryable_image_error(last_error):
                        raise
                    time.sleep(1.2 * (idx + 1))
            if obj is None:
                error = _format_image_test_error(last_error)
                return ImageTestOut(ok=False, error=error, message=_image_test_failure_message(error))
            return ImageTestOut(ok=True, data=obj, message="测试成功：生图模型可用。")
        except Exception as e:
            error = _format_image_test_error(str(e))
            return ImageTestOut(ok=False, error=error, message=_image_test_failure_message(error))
