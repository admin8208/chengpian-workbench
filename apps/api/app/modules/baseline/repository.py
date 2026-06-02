from __future__ import annotations

import json

from sqlmodel import Session, select

from app.models import Project
from app.models_revisions import ContentBaselineRevision
from app.time_utils import now_utc


def create_baseline_revision(
    session: Session,
    *,
    project: Project,
    input_mode: str,
    script_text: str,
    source: str,
    audio_asset_id: int | None = None,
    timing: dict | None = None,
    status: str = "draft",
) -> ContentBaselineRevision:
    if project.id is None:
        raise ValueError("project id is required")
    if status == "confirmed":
        old_rows = session.exec(
            select(ContentBaselineRevision).where(
                ContentBaselineRevision.project_id == int(project.id),
                ContentBaselineRevision.status == "confirmed",
            )
        ).all()
        for row in old_rows:
            row.status = "superseded"
            row.updated_at = now_utc()
            session.add(row)
    rev = ContentBaselineRevision(
        project_id=int(project.id),
        input_mode=("audio" if input_mode == "audio" else "text"),
        script_text=str(script_text or "").strip(),
        audio_asset_id=audio_asset_id,
        timing_json=json.dumps(timing or {}, ensure_ascii=True),
        source=str(source or "").strip(),
        status=status,
    )
    session.add(rev)
    session.flush()
    session.refresh(rev)
    return rev


def latest_confirmed_baseline(session: Session, project_id: int) -> ContentBaselineRevision | None:
    rows = session.exec(
        select(ContentBaselineRevision)
        .where(ContentBaselineRevision.project_id == int(project_id), ContentBaselineRevision.status == "confirmed")
        .order_by(ContentBaselineRevision.id.desc())
    ).all()
    return rows[0] if rows else None
