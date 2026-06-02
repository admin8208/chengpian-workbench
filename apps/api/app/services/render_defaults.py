from app.models import Project


LANDSCAPE_DIMENSIONS = (1664, 944)
PORTRAIT_DIMENSIONS = (944, 1664)


def default_visual_strategy_for_channel(channel_key: str | None) -> str:
    return "scene_rich"


def normalize_render_aspect(aspect: str | None) -> str:
    return "portrait" if str(aspect or "").strip().lower() == "portrait" else "landscape"


def default_render_dimensions(aspect: str | None) -> tuple[int, int]:
    return PORTRAIT_DIMENSIONS if normalize_render_aspect(aspect) == "portrait" else LANDSCAPE_DIMENSIONS


def project_render_aspect(p: Project) -> str:
    cfg = p.render_config() if hasattr(p, "render_config") else {}
    return normalize_render_aspect(str((cfg or {}).get("aspect") or ""))


def project_visual_strategy(p: Project) -> str:
    return "scene_rich"
