from __future__ import annotations

import json

from sqlmodel import select

from app.db import session_scope
from app.models import Project, Scene
from app.models_revisions import ContentBaselineRevision
from app.modules.storyboard.repository import create_storyboard_revision, replace_project_scenes
from app.material_policies import project_material_mode
from app.time_utils import now_utc


def save_storyboard(pid: int, script: str, scenes: list[dict], *, update_project_status: bool) -> bool:
    with session_scope() as session:
        project = session.exec(select(Project).where(Project.id == pid)).first()
        if not project:
            return False
        baseline_revision_id = int(getattr(project, "confirmed_baseline_revision_id", 0) or 0)
        if baseline_revision_id <= 0:
            draft = session.exec(
                select(ContentBaselineRevision)
                .where(ContentBaselineRevision.project_id == int(pid))
                .order_by(ContentBaselineRevision.id.desc())
            ).all()
            if draft:
                baseline_revision_id = int(draft[0].id or 0)
        storyboard_revision_id = 0
        if baseline_revision_id > 0:
            revision = create_storyboard_revision(
                session,
                project=project,
                baseline_revision_id=baseline_revision_id,
                material_mode=project_material_mode(project),
                scenes=scenes,
                meta={"script_length": len(str(script or ""))},
            )
            storyboard_revision_id = int(revision.id or 0)
        if not getattr(project, "confirmed_baseline_revision_id", None):
            project.script = script
        if update_project_status:
            project.status = "processing"
        project.updated_at = now_utc()
        session.add(project)
        replace_project_scenes(session, project_id=pid, storyboard_revision_id=storyboard_revision_id, scenes=scenes)
    return True
