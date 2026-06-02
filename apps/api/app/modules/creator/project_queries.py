from fastapi import HTTPException
from sqlalchemy import desc
from sqlmodel import select

from app.access_control import visible_project_query
from app.db import session_scope
from app.models import Project
from app.schemas import ProjectOut


def list_projects_api(project_to_out, workflow: str = "") -> list[ProjectOut]:
    with session_scope() as session:
        query = select(Project)
        wf = (workflow or "").strip().lower()
        if wf:
            if wf != "mix":
                raise HTTPException(status_code=400, detail="当前仅支持 mix 工作流")
            query = query.where(Project.workflow == "mix")
        query = visible_project_query(query)
        items = session.exec(query.order_by(desc(Project.created_at))).all()
        return [project_to_out(session, project) for project in items if project.id is not None]
