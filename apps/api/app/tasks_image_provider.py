import base64
import os
import time
from pathlib import Path
from urllib.parse import urlparse

from app.http_client import new_session
from app.prompts import build_image_prompts


SUPPORTED_IMAGE_SIZES = ("1664x944", "944x1664", "1024x1024")


def normalize_image_size(project) -> str:
    aspect = "landscape"
    width = 0
    height = 0
    try:
        cfg = project.render_config() if project and hasattr(project, "render_config") else {}
        if not isinstance(cfg, dict):
            cfg = {}
        aspect = str(cfg.get("aspect") or "landscape").strip().lower() or "landscape"
        width = int(cfg.get("width") or 0)
        height = int(cfg.get("height") or 0)
    except Exception:
        aspect = "landscape"
        width = 0
        height = 0

    if aspect == "portrait" or (height > width > 0):
        return "944x1664"
    return "1664x944"


def image_size_candidates(project) -> list[str]:
    primary = normalize_image_size(project)
    if primary == "944x1664":
        ordered = ["944x1664", "1024x1024"]
    else:
        ordered = ["1664x944", "1024x1024"]
    out: list[str] = []
    for size in ordered:
        if size in SUPPORTED_IMAGE_SIZES and size not in out:
            out.append(size)
    return out


def image_generate_timeout_s() -> int:
    try:
        return max(20, int(os.environ.get("CHENGPIAN_IMAGE_TIMEOUT_S", "600") or "600"))
    except Exception:
        return 600


def image_generate_attempts() -> int:
    try:
        return max(1, min(4, int(os.environ.get("CHENGPIAN_IMAGE_ATTEMPTS", "2") or "2")))
    except Exception:
        return 2


def image_rich_prompt_timeout_s(timeout_s: int) -> int:
    return max(60, int(timeout_s or image_generate_timeout_s()))


def scene_prompt_for_provider(pack, scene) -> str:
    aspect = "portrait" if str(getattr(scene, "project_aspect", "") or "").strip().lower() == "portrait" else "landscape"
    positive, _negative = build_image_prompts(pack, scene, with_quality_booster=True, with_character_lock=True, aspect=aspect)
    return positive


def scene_negative_for_provider(pack, scene) -> str:
    aspect = "portrait" if str(getattr(scene, "project_aspect", "") or "").strip().lower() == "portrait" else "landscape"
    _positive, negative = build_image_prompts(pack, scene, with_quality_booster=True, with_character_lock=True, aspect=aspect)
    return negative


def scene_prompt_fallback_for_provider(pack, scene) -> str:
    cfg = pack.config() if hasattr(pack, "config") else (pack if isinstance(pack, dict) else {})
    style = str(cfg.get("style", "cinematic realism")).strip() or "cinematic realism"
    narration = str(getattr(scene, "narration", "") or "").strip()
    scene_prompt = str(getattr(scene, "image_prompt", "") or "").strip()
    aspect = "portrait" if str(getattr(scene, "project_aspect", "") or "").strip().lower() == "portrait" else "landscape"
    parts = [style, "realistic", "cinematic", "9:16" if aspect == "portrait" else "16:9", "medium close shot"]
    if narration:
        parts.append(narration)
    if scene_prompt:
        parts.append(scene_prompt)
    return ", ".join([p for p in parts if p]).strip(" ,")


def download_or_decode_image(obj: dict) -> tuple[bytes, str]:
    b64 = str(obj.get("b64_json") or "").strip()
    if b64:
        return base64.b64decode(b64), "image/png"
    url = str(obj.get("url") or "").strip()
    if not url:
        raise RuntimeError("生图服务没有返回可保存的图片数据")
    response = new_session(headers={"Accept": "image/*,*/*"}).get(url, timeout=image_generate_timeout_s())
    if not response.ok:
        raise RuntimeError(f"下载生成图片失败：{response.status_code}")
    mime = str(response.headers.get("Content-Type") or "image/png").split(";")[0].strip() or "image/png"
    return response.content, mime


def guess_image_ext(mime: str, obj: dict) -> str:
    low = str(mime or "").strip().lower()
    if "jpeg" in low or "jpg" in low:
        return ".jpg"
    if "webp" in low:
        return ".webp"
    if "png" in low:
        return ".png"
    url = str(obj.get("url") or "").strip()
    if url:
        suffix = Path(urlparse(url).path).suffix.lower()
        if suffix in (".png", ".jpg", ".jpeg", ".webp"):
            return ".jpg" if suffix == ".jpeg" else suffix
    return ".png"


def is_retryable_image_generation_error(detail: str) -> bool:
    low = str(detail or "").lower()
    return any(token in low for token in ("error 520", '"status":520', " 520", "timeout", "timed out", "502", "503", "504", '"retryable":true'))


def is_provider_switchable_image_error(detail: str) -> bool:
    low = str(detail or '').lower()
    return any(token in low for token in (
        'rate_limit_exceeded',
        'model_not_found',
        'new_api_error',
        'database error',
        'no available channel',
        'daily usage limit',
        '每日使用上限',
        '服务处理超时',
        'timeout',
        'timed out',
        '502',
        '503',
        '504',
    ))


def is_size_retryable_image_error(detail: str) -> bool:
    low = str(detail or "").lower()
    return any(token in low for token in (
        "invalid_size",
        "unsupported size",
        "size not supported",
        "unsupported resolution",
        "invalid image size",
        "resolution not supported",
        "does not support size",
        "400",
        "invalid_argument",
    ))


def generate_scene_image_via_provider(*, session, provider, providers, get_image_api_key, api_key: str, project, pack, scene, openai_compat_generate_image) -> tuple[bytes, str, dict]:
    project_aspect = "portrait" if str((project.render_config() if project and hasattr(project, "render_config") else {}).get("aspect") or "").strip().lower() == "portrait" else "landscape"
    setattr(scene, "project_aspect", project_aspect)
    prompt = scene_prompt_for_provider(pack, scene)
    negative_prompt = scene_negative_for_provider(pack, scene)
    fallback_prompt = scene_prompt_fallback_for_provider(pack, scene)
    timeout_s = image_generate_timeout_s()
    requested_sizes = image_size_candidates(project)
    last_error = ''
    chosen_provider = provider
    obj = None
    chosen_size = requested_sizes[0] if requested_sizes else normalize_image_size(project)
    used_prompt = prompt
    used_negative_prompt = negative_prompt
    current_provider = provider
    current_api_key = api_key
    if str(getattr(current_provider, 'type', '') or '') == 'openai_compat' and not str(current_api_key or '').strip():
        raise RuntimeError('未设置 API Key')
    current_error = ''
    for requested_size in requested_sizes:
        attempts = image_generate_attempts()
        for idx in range(attempts):
            prompt_variants = [(prompt, negative_prompt)]
            if fallback_prompt and fallback_prompt != prompt:
                prompt_variants.append((fallback_prompt, ''))
            for prompt_value, negative_value in prompt_variants:
                try:
                    current_timeout_s = timeout_s if (prompt_value, negative_value) != (prompt, negative_prompt) else image_rich_prompt_timeout_s(timeout_s)
                    obj = openai_compat_generate_image(
                        base_url=str(current_provider.base_url or '').strip(),
                        api_key=current_api_key,
                        model=str(current_provider.default_model or '').strip(),
                        prompt=prompt_value,
                        negative_prompt=negative_value,
                        size=requested_size,
                        timeout_s=current_timeout_s,
                    )
                    chosen_provider = current_provider
                    chosen_size = requested_size
                    used_prompt = prompt_value
                    used_negative_prompt = negative_value
                    break
                except Exception as exc:
                    current_error = str(exc)
                    last_error = current_error
                    if (prompt_value, negative_value) != (prompt, negative_prompt):
                        continue
                    if idx < attempts - 1 and is_retryable_image_generation_error(current_error):
                        time.sleep(4 * (idx + 1))
                        continue
                if obj is not None:
                    break
            if obj is None and current_error and not is_retryable_image_generation_error(current_error):
                break
            if obj is not None:
                break
        if obj is not None:
            break
        if current_error and not is_size_retryable_image_error(current_error):
            break
    if obj is None:
        raise RuntimeError(last_error or "生图服务没有返回结果")
    image_bytes, mime = download_or_decode_image(obj if isinstance(obj, dict) else {})
    meta = {
        "source": "ai_generated",
        "provider_id": int(chosen_provider.id),
        "provider_name": str(chosen_provider.name or ""),
        "provider_type": str(chosen_provider.type or ""),
        "model": str(chosen_provider.default_model or ""),
        "material_mode": "ai",
        "prompt": used_prompt,
        "negative_prompt": used_negative_prompt,
        "size": chosen_size,
        "image_url": str((obj or {}).get("url") or ""),
    }
    return image_bytes, mime, meta
