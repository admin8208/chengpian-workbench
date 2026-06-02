from __future__ import annotations

from app.modules.baseline.service import prepare_project_script


def prepare_project_script_task(project_id: int) -> None:
    prepare_project_script(project_id, project_to_out=lambda _session, project: project)
