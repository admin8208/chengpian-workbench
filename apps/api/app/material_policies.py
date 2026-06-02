import json


def normalize_material_mode(value) -> str:
    mode = str(value or "network").strip().lower()
    return "ai" if mode == "ai" else "network"


def project_material_mode(project=None, render_cfg: dict | None = None) -> str:
    cfg = render_cfg if isinstance(render_cfg, dict) else {}
    if not cfg and project is not None and hasattr(project, "render_config"):
        try:
            cfg = project.render_config()
        except Exception:
            cfg = {}
    return normalize_material_mode((cfg or {}).get("material_mode"))


def asset_material_mode(asset=None, meta: dict | None = None) -> str:
    obj = meta if isinstance(meta, dict) else {}
    if not obj and asset is not None:
        try:
            obj = json.loads(getattr(asset, "meta_json", "{}") or "{}")
            if not isinstance(obj, dict):
                obj = {}
        except Exception:
            obj = {}
    rel_path = str(getattr(asset, "rel_path", "") or "").strip().lower() if asset is not None else ""
    mode = normalize_material_mode(obj.get("material_mode"))
    pipeline = str(obj.get("media_pipeline") or "").strip().lower()
    generated_by = str(obj.get("generated_by") or "").strip().lower()
    if mode == "ai" or pipeline == "ai_image" or generated_by == "image_provider" or (rel_path.startswith("project_") and "/generated/" in rel_path):
        return "ai"
    return "network"


def scene_binding_material_mode(scene=None, meta: dict | None = None) -> str | None:
    obj = meta if isinstance(meta, dict) else {}
    if not obj and scene is not None:
        try:
            obj = json.loads(getattr(scene, "meta_json", "{}") or "{}")
            if not isinstance(obj, dict):
                obj = {}
        except Exception:
            obj = {}
    raw = obj.get("binding_material_mode") or obj.get("bound_asset_material_mode") or obj.get("project_material_mode")
    if raw is None:
        return None
    return normalize_material_mode(raw)


def material_mode_label(mode: str) -> str:
    return "智能生图模式" if normalize_material_mode(mode) == "ai" else "素材模式"


def asset_mode_label(mode: str) -> str:
    return "AI 镜头图" if normalize_material_mode(mode) == "ai" else "素材库素材"
