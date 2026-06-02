"""LLM provider router extracted from the main application entrypoint."""

from fastapi import APIRouter, HTTPException
from sqlmodel import select
import time

from app.db import session_scope
from app.llm_client import LlmChatMessage, normalize_provider_base_url, ollama_chat_json, openai_compat_chat_json
from app.llm_service import get_api_key, get_default_provider, has_api_key, normalize_llm_providers, set_default_provider, upsert_api_key, upsert_provider
from app.models import LlmProvider
from app.schemas import LlmKeyIn, LlmProviderIn, LlmProviderOut, LlmStatusOut, LlmTestIn, LlmTestOut

router = APIRouter(tags=["llm"])


def _llm_test_failure_message(detail: str) -> str:
    raw = str(detail or "").strip()
    low = raw.lower()
    if "api key" in low or "鉴权" in raw or "unauthorized" in low or "401" in low:
        return "测试失败：大模型鉴权失败（401），请检查 API Key。"
    if "403" in low or "forbidden" in low or "permission denied" in low or "拒绝访问" in raw:
        return "测试失败：大模型拒绝访问（403），请检查账号权限、模型权限或风控策略。"
    if "429" in low or "rate limit" in low or "quota" in low:
        return "测试失败：大模型请求被限流或额度不足（429）。"
    if "model" in low and ("not" in low or "empty" in low or "模型" in raw):
        return "测试失败：大模型模型名不可用，请检查模型名称。"
    if "timeout" in low or "timed out" in low or "超时" in raw:
        return "测试失败：大模型响应超时，请检查服务地址、模型名或服务商状态。"
    if "json" in low or "解析" in raw:
        return "测试失败：大模型返回格式不符合系统要求，请更换模型或调整服务商配置。"
    if any(token in low for token in ("502", "503", "504")):
        return "测试失败：大模型上游服务异常（5xx），请稍后重试。"
    if "接口地址不能为空" in raw or "base_url" in low:
        return "测试失败：请填写大模型服务地址。"
    if "模型名不能为空" in raw:
        return "测试失败：请填写大模型模型名。"
    if raw:
        return f"测试失败：{raw}"
    return "测试失败：大模型不可用，请检查服务地址、模型名或 API Key。"


def provider_to_out(p: LlmProvider, api_key: str = "") -> LlmProviderOut:
    return LlmProviderOut(
        id=int(p.id),
        name=p.name,
        type=p.type,
        base_url=p.base_url,
        default_model=p.default_model,
        enabled=bool(p.enabled),
        is_default=bool(p.is_default),
        api_key=api_key if p.type != "ollama" else "",
    )


@router.get("/api/llm/status", response_model=LlmStatusOut)
def llm_status():
    with session_scope() as session:
        p = get_default_provider(session)
        if not p or p.id is None:
            return LlmStatusOut(has_default=False)
        key_ok = True if p.type == "ollama" else has_api_key(session, int(p.id))
        return LlmStatusOut(
            has_default=True,
            default_provider_id=int(p.id),
            default_provider_name=p.name,
            default_provider_type=p.type,
            default_model=p.default_model,
            has_api_key=key_ok,
        )

@router.get("/api/llm/providers", response_model=list[LlmProviderOut])
def list_llm_providers():
    with session_scope() as session:
        normalize_llm_providers(session)
        items = session.exec(select(LlmProvider).order_by(LlmProvider.id)).all()
        return [provider_to_out(p, get_api_key(session, int(p.id)) if p.type != "ollama" else "") for p in items if p.id is not None]


@router.post("/api/llm/providers", response_model=LlmProviderOut)
def create_llm_provider(body: LlmProviderIn):
    if body.type not in ("openai_compat", "ollama"):
        raise HTTPException(status_code=400, detail="type 只能是 openai_compat 或 ollama")
    normalized_base_url = normalize_provider_base_url(body.type, body.base_url)
    with session_scope() as session:
        normalize_llm_providers(session)
        p = upsert_provider(
            session,
            name=body.name,
            type_=body.type,
            base_url=normalized_base_url,
            default_model=body.default_model.strip(),
            enabled=bool(body.enabled),
            is_default=bool(body.is_default),
        )
        if p.type != "ollama" and body.api_key.strip():
            upsert_api_key(session, int(p.id), body.api_key)
        if p.is_default:
            set_default_provider(session, int(p.id))
        normalize_llm_providers(session)
        session.flush()
        session.refresh(p)
        return provider_to_out(p, get_api_key(session, int(p.id)) if p.type != "ollama" else "")


@router.post("/api/llm/providers/{provider_id}/key")
def set_llm_key(provider_id: int, body: LlmKeyIn):
    with session_scope() as session:
        p = session.exec(select(LlmProvider).where(LlmProvider.id == provider_id)).first()
        if not p or p.id is None:
            raise HTTPException(status_code=404, detail="provider 不存在")
        if p.type == "ollama":
            return {"ok": True, "note": "Ollama 不需要 API Key"}
        upsert_api_key(session, int(p.id), body.api_key)
    return {"ok": True}


@router.post("/api/llm/test", response_model=LlmTestOut)
def test_llm(body: LlmTestIn):
    with session_scope() as session:
        try:
            started = time.perf_counter()
            prompt = str(body.prompt or "").strip() or '请只返回 {"ok":true}'
            messages = [
                LlmChatMessage(role="system", content='只返回严格 JSON，不要 Markdown，不要解释。JSON 格式必须是：{"ok":true}'),
                LlmChatMessage(role="user", content=prompt[:500]),
            ]
            p = session.exec(select(LlmProvider).where(LlmProvider.id == body.provider_id)).first() if body.provider_id else None
            provider_type = str((body.type or getattr(p, "type", "") or "openai_compat")).strip()
            base_url = normalize_provider_base_url(provider_type, str((body.base_url or getattr(p, "base_url", "") or "")).strip())
            default_model = str((body.default_model or getattr(p, "default_model", "") or "")).strip()
            if not base_url:
                message = _llm_test_failure_message("接口地址不能为空")
                return LlmTestOut(ok=False, error="接口地址不能为空", message=message)
            if not default_model:
                message = _llm_test_failure_message("模型名不能为空")
                return LlmTestOut(ok=False, error="模型名不能为空", message=message)
            if provider_type == "ollama":
                obj = ollama_chat_json(base_url=base_url, model=default_model, messages=messages, timeout_s=30)
            else:
                key = str(body.api_key or "").strip() or (get_api_key(session, int(p.id)) if p and p.id is not None else "")
                if not key:
                    message = _llm_test_failure_message("未设置 API Key")
                    return LlmTestOut(ok=False, error="未设置 API Key", message=message)
                obj = openai_compat_chat_json(
                    base_url=base_url,
                    api_key=key,
                    model=default_model,
                    messages=messages,
                    timeout_s=30,
                    max_tokens=128,
                    temperature=0.2,
                )
            elapsed = time.perf_counter() - started
            return LlmTestOut(ok=True, data=obj, message=f"测试成功：大模型可用，耗时 {elapsed:.1f} 秒。")
        except Exception as e:
            detail = str(e)
            return LlmTestOut(ok=False, error=detail, message=_llm_test_failure_message(detail))
