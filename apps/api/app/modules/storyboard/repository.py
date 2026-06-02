from __future__ import annotations

import json

from sqlmodel import Session, select

from app.models import Project, Scene
from app.models_revisions import StoryboardRevision
from app.time_utils import now_utc


def create_storyboard_revision(
    session: Session,
    *,
    project: Project,
    baseline_revision_id: int,
    material_mode: str,
    scenes: list[dict],
    meta: dict | None = None,
) -> StoryboardRevision:
    if project.id is None:
        raise ValueError("project id is required")
    old_rows = session.exec(
        select(StoryboardRevision).where(
            StoryboardRevision.project_id == int(project.id),
            StoryboardRevision.status == "ready",
        )
    ).all()
    for row in old_rows:
        row.status = "stale"
        row.updated_at = now_utc()
        session.add(row)
    rev = StoryboardRevision(
        project_id=int(project.id),
        baseline_revision_id=int(baseline_revision_id),
        material_mode=("ai" if material_mode == "ai" else "network"),
        status="ready",
        scene_count=len(scenes),
        meta_json=json.dumps(meta or {}, ensure_ascii=True),
    )
    session.add(rev)
    session.flush()
    session.refresh(rev)
    return rev


def replace_project_scenes(session: Session, *, project_id: int, storyboard_revision_id: int, scenes: list[dict]) -> None:
    old = session.exec(select(Scene).where(Scene.project_id == int(project_id))).all()
    for s in old:
        session.delete(s)
    for s in scenes:
        try:
            meta = s.get("meta") if isinstance(s.get("meta"), dict) else {}
            sc = Scene(
                project_id=int(project_id),
                storyboard_revision_id=int(storyboard_revision_id),
                idx=int(s.get("idx", 0) or 0),
                narration=str(s.get("narration", "") or "").strip(),
                media_query=str(s.get("media_query") or s.get("narration") or "").strip()[:120],
                image_prompt=str(s.get("image_prompt", "") or "").strip(),
                image_negative=str(s.get("image_negative", "") or "").strip(),
                duration_sec=float(s.get("duration_sec", 6) or 6),
                meta_json=json.dumps(meta, ensure_ascii=True),
                status="pending",
            )
            if sc.idx <= 0:
                continue
            session.add(sc)
        except Exception:
            continue
