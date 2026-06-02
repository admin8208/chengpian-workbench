from sqlmodel import select

from app.db import session_scope
from app.models import Scene


def check_render_quality(project_id: int) -> dict:
    """Check if project is ready for rendering. Returns quality gates status."""
    with session_scope() as session:
        scenes = session.exec(select(Scene).where(Scene.project_id == project_id)).all()
        if not scenes:
            return {"ready": False, "reason": "no_scenes", "details": {}}

        missing_count = 0
        asset_ids: list[int] = []
        for scene in scenes:
            if not scene.image_asset_id:
                missing_count += 1
            else:
                asset_ids.append(scene.image_asset_id)

        duplicate_count = len(asset_ids) - len(set(asset_ids)) if asset_ids else 0
        gates = {
            "missing_assets": {"count": missing_count, "threshold": 0, "pass": missing_count <= 0},
            "duplicates": {"count": duplicate_count, "threshold": 3, "pass": duplicate_count <= 3},
        }
        all_pass = all(gate["pass"] for gate in gates.values())
        return {
            "ready": all_pass,
            "reason": "quality_gates_failed" if not all_pass else "ok",
            "gates": gates,
            "total_scenes": len(scenes),
            "suggestions": _generate_quality_suggestions(gates),
        }


def _generate_quality_suggestions(gates: dict) -> list[str]:
    suggestions: list[str] = []
    if not gates["missing_assets"]["pass"]:
        suggestions.append(f"缺少 {gates['missing_assets']['count']} 个镜头素材，请先搜索补齐")
    if not gates["duplicates"]["pass"]:
        suggestions.append(f"检测到 {gates['duplicates']['count']} 个重复素材，建议更换")
    return suggestions
