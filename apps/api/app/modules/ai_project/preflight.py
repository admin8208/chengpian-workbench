from __future__ import annotations

from app.image_service import get_default_image_provider, get_image_api_key


def ai_media_preflight(session, project=None):
    image_provider = get_default_image_provider(session)
    if not image_provider or image_provider.id is None or not bool(getattr(image_provider, "enabled", True)):
        return (False, {"message": "未配置默认生图模型（设置->生图模型）", "error_code": "image_config_missing", "blocking_component": "image", "recommended_action": "go_settings_image", "recoverable": True})
    image_api_key = get_image_api_key(session, int(image_provider.id))
    if str(image_provider.type or "") == "openai_compat" and not str(image_api_key or "").strip():
        return (False, {"message": "未设置生图接口密钥（设置 -> 生图模型）", "error_code": "image_config_missing", "blocking_component": "image", "recommended_action": "go_settings_image", "recoverable": True})
    if not str(image_provider.base_url or "").strip():
        return (False, {"message": "生图服务地址未配置（设置 -> 生图模型）", "error_code": "image_config_missing", "blocking_component": "image", "recommended_action": "go_settings_image", "recoverable": True})
    if not str(image_provider.default_model or "").strip():
        return (False, {"message": "生图模型名称未配置（设置 -> 生图模型）", "error_code": "image_config_missing", "blocking_component": "image", "recommended_action": "go_settings_image", "recoverable": True})
    return (True, {})
