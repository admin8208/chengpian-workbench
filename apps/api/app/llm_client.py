
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests
from loguru import logger

from app.http_client import new_session


class LlmError(RuntimeError):
    pass


@dataclass(frozen=True)
class LlmChatMessage:
    role: str  # system|user|assistant
    content: str


def normalize_provider_base_url(provider_type: str, base_url: str) -> str:
    normalized = str(base_url or "").strip().rstrip("/")
    if not normalized:
        return ""
    low = normalized.lower()
    if str(provider_type or "").strip().lower() == "ollama":
        if low.endswith("/api/chat"):
            return normalized[: -len("/api/chat")]
        return normalized
    suffixes = (
        "/v1/chat/completions",
        "/chat/completions",
        "/v1/images/generations",
        "/images/generations",
        "/v1/models",
        "/models",
    )
    for suffix in suffixes:
        if low.endswith(suffix):
            return normalized[: -len(suffix)].rstrip("/")
    return normalized


def _strip_markup_blocks(text: str) -> str:
    cleaned = str(text or "")
    cleaned = re.sub(r"<system-reminder\b[^>]*>.*?</system-reminder>", " ", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _llm_http_error_message(status_code: int, raw_text: str) -> str:
    cleaned = _strip_markup_blocks(raw_text)
    low = cleaned.lower()
    if status_code == 401:
        return "大模型服务鉴权失败（401），请检查 API Key"
    if status_code == 403:
        return "大模型服务拒绝访问（403），请检查账号权限、模型权限或风控策略"
    if status_code == 404:
        return "大模型服务地址或接口路径不存在，请检查 base_url 配置"
    if status_code == 405:
        return "大模型服务接口方法不支持，请检查 base_url 是否配置到了正确的 API 路径"
    if status_code == 429:
        return "大模型请求被限流或额度不足（429），请稍后重试"
    if status_code >= 500:
        return f"大模型上游服务异常（HTTP {status_code}），请稍后重试"
    if cleaned:
        return cleaned[:300]
    if "method not allowed" in low:
        return "大模型服务接口方法不支持，请检查 base_url 是否配置到了正确的 API 路径"
    return f"大模型请求失败（HTTP {status_code}）"


def _raise_for_llm_response(r) -> None:
    if r.ok:
        return
    raise LlmError(_llm_http_error_message(int(getattr(r, "status_code", 0) or 0), getattr(r, "text", "")))


def _join_url(base_url: str, path: str) -> str:
    base = (base_url or "").rstrip("/")
    p = path.lstrip("/")
    return f"{base}/{p}"


def _openai_chat_url(base_url: str) -> str:
    base_url = normalize_provider_base_url("openai_compat", base_url)
    # Accept base_url as either https://host or https://host/v1
    if base_url.rstrip("/").endswith("/v1"):
        return _join_url(base_url, "chat/completions")
    return _join_url(base_url, "v1/chat/completions")


def _openai_images_url(base_url: str) -> str:
    base_url = normalize_provider_base_url("openai_compat", base_url)
    if base_url.rstrip("/").endswith("/v1"):
        return _join_url(base_url, "images/generations")
    return _join_url(base_url, "v1/images/generations")


def _default_timeout_s(default: int) -> int:
    try:
        return max(15, int(os.environ.get("CHENGPIAN_LLM_TIMEOUT_S", str(default)) or default))
    except Exception:
        return default


def _timeout_tuple(default: int) -> tuple[int, int]:
    total = _default_timeout_s(default)
    connect = max(10, min(20, total))
    read = max(15, total)
    return (connect, read)


def _request_with_timeout(fn, timeout_s: int):
    try:
        return fn()
    except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout, requests.exceptions.Timeout):
        raise LlmError(f"request timeout after {_default_timeout_s(timeout_s)}s")
    except requests.exceptions.RequestException as exc:
        raise LlmError(f"request failed: {exc}") from exc


def _safe_url_host(url: str) -> str:
    try:
        parsed = urlparse(str(url or ""))
        return parsed.netloc or parsed.path.split("/", 1)[0]
    except Exception:
        return ""


def _strip_code_fence(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t.replace("json\n", "", 1).replace("JSON\n", "", 1)
    return t.strip()


def _coerce_non_json_text(text: str) -> dict[str, Any] | None:
    t = _strip_code_fence(text)
    if not t:
        return None
    lower = t.lower()
    if any(token in lower for token in ("<html", "<!doctype", "<body", "<head")):
        return None
    refusal_prefixes = ("抱歉", "对不起", "很抱歉", "sorry", "i'm sorry", "i am sorry", "as an ai", "as a language model")
    error_markers = ("error", "exception", "traceback", "bad gateway", "service unavailable", "unauthorized", "forbidden")
    refusal_markers = ("无法", "不能", "不可以", "cannot", "can't", "not able", "unable to")
    if lower.startswith(refusal_prefixes) and any(marker in lower or marker in t for marker in refusal_markers):
        return None
    if len(t) < 120 and any(marker in lower for marker in error_markers):
        return None

    script_match = re.match(r"(?is)^script\s*[:：]\s*(.+)$", t)
    if script_match:
        script = script_match.group(1).strip()
        if script:
            return {"script": script}

    raw_lines = [line.strip() for line in t.splitlines() if line.strip()]
    bullet_lines = [re.sub(r"^(?:[-*]|\d+[.)]|[一二三四五六七八九十]+[、.])\s*", "", line).strip() for line in raw_lines]
    bullet_lines = [line for line in bullet_lines if line]
    if len(bullet_lines) >= 2:
        return {"lines": bullet_lines}

    if len(t) >= 20:
        return {"script": t}
    return None


def openai_compat_chat_json(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[LlmChatMessage],
    timeout_s: int = 600,
    max_tokens: int | None = None,
    temperature: float = 0.7,
) -> dict[str, Any]:
    url = _openai_chat_url(base_url)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max(1, int(max_tokens))
    started = time.perf_counter()
    try:
        r = _request_with_timeout(lambda: new_session(headers=headers).post(url, json=payload, timeout=_timeout_tuple(timeout_s)), timeout_s)
    finally:
        logger.info(
            "llm chat request finished provider=openai_compat host={} model={} timeout_s={} max_tokens={} elapsed_s={:.3f}",
            _safe_url_host(url),
            model,
            timeout_s,
            max_tokens,
            time.perf_counter() - started,
        )
    _raise_for_llm_response(r)
    data = r.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception:
        raise LlmError(f"unexpected response: {data}")
    return _parse_json_from_text(content)


def openai_compat_generate_image(
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    negative_prompt: str = "",
    size: str = "1664x944",
    timeout_s: int = 600,
) -> dict[str, Any]:
    url = _openai_images_url(base_url)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "n": 1,
        "response_format": "b64_json",
    }
    if str(negative_prompt or "").strip():
        payload["negative_prompt"] = str(negative_prompt).strip()
    r = _request_with_timeout(lambda: new_session(headers=headers).post(url, json=payload, timeout=_timeout_tuple(timeout_s)), timeout_s)
    _raise_for_llm_response(r)
    data = r.json()
    if not isinstance(data, dict):
        raise LlmError(f"unexpected response: {data}")
    items = data.get("data")
    if not isinstance(items, list) or not items:
        raise LlmError(f"unexpected response: {data}")
    first = items[0] if isinstance(items[0], dict) else {}
    out: dict[str, Any] = {
        "created": data.get("created"),
        "has_url": bool(first.get("url")),
        "has_b64": bool(first.get("b64_json")),
        "mime": "image/png",
    }
    if first.get("url"):
        out["url"] = str(first.get("url"))
    if first.get("b64_json"):
        out["b64_json"] = str(first.get("b64_json"))
    return out


def openai_compat_list_models(
    *,
    base_url: str,
    api_key: str,
    timeout_s: int = 600,
) -> list[str]:
    base_url = normalize_provider_base_url("openai_compat", base_url)
    if base_url.rstrip("/").endswith("/v1"):
        url = _join_url(base_url, "models")
    else:
        url = _join_url(base_url, "v1/models")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    r = _request_with_timeout(lambda: new_session(headers=headers).get(url, timeout=_timeout_tuple(timeout_s)), timeout_s)
    _raise_for_llm_response(r)
    data = r.json()
    items = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise LlmError(f"unexpected response: {data}")
    out: list[str] = []
    for item in items:
        if isinstance(item, dict) and item.get("id"):
            out.append(str(item.get("id")))
    return out


def ollama_chat_json(
    *,
    base_url: str,
    model: str,
    messages: list[LlmChatMessage],
    timeout_s: int = 600,
) -> dict[str, Any]:
    base_url = normalize_provider_base_url("ollama", base_url)
    url = _join_url(base_url, "api/chat")
    payload = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "stream": False,
        "format": "json",
    }
    r = _request_with_timeout(lambda: new_session().post(url, json=payload, timeout=_timeout_tuple(timeout_s)), timeout_s)
    _raise_for_llm_response(r)
    data = r.json()
    content = (data.get("message") or {}).get("content")
    if not content:
        raise LlmError(f"unexpected response: {data}")
    return _parse_json_from_text(content)


def _parse_json_from_text(text: str) -> dict[str, Any]:
    t = _strip_code_fence(text)
    # If model wrapped JSON in code-fences, strip them.
    # Best-effort: locate the first { and last }.
    if "{" in t and "}" in t:
        start = t.find("{")
        end = t.rfind("}")
        t = t[start : end + 1]

    try:
        obj = json.loads(t)
    except Exception as e:
        fallback = _coerce_non_json_text(text)
        if fallback is not None:
            return fallback
        raise LlmError(f"JSON 解析失败：{e}; 原始内容={text[:300]}")

    if isinstance(obj, dict):
        return obj
    if isinstance(obj, list):
        if obj and all(isinstance(item, dict) for item in obj):
            return {"scenes": obj}
        lines = [str(item).strip() for item in obj if str(item).strip()]
        if lines:
            return {"lines": lines}
    if isinstance(obj, str):
        script = obj.strip()
        if script:
            return {"script": script}
    fallback = _coerce_non_json_text(text)
    if fallback is not None:
        return fallback
    raise LlmError("response JSON is not an object")
