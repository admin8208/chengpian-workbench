from __future__ import annotations

from app.material_policies import normalize_material_mode
from app.modules.ai_project.summary_service import ai_summary_strategy
from app.modules.network_project.summary_service import network_summary_strategy
from app.modules.project_summary.types import ProjectSummaryStrategy


def resolve_project_summary_strategy(material_mode: str) -> ProjectSummaryStrategy:
    return ai_summary_strategy if normalize_material_mode(material_mode) == "ai" else network_summary_strategy
