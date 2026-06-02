from __future__ import annotations

import sys
from pathlib import Path

from sqlmodel import select


# Allow running this script from anywhere by adding apps/api to sys.path.
ROOT_DIR = Path(__file__).resolve().parents[2]
API_DIR = ROOT_DIR / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.db import init_db, session_scope
from app.models import Job, Project, Scene
from app.seed import seed_channel_packs
from app.tasks import generate_storyboard


def main() -> None:
    init_db()
    seed_channel_packs()

    with session_scope() as session:
        p = Project(title="Smoke Test", channel_key="history", status="draft")
        session.add(p)
        session.flush()
        session.refresh(p)
        pid = int(p.id)

        j = Job(kind="storyboard", project_id=pid, status="queued", progress=0, message="")
        session.add(j)
        session.flush()
        session.refresh(j)
        jid = int(j.id)

    print("created", pid, jid)

    # Run synchronously without worker
    generate_storyboard.call_local(jid, pid, topic="Smoke Topic")

    with session_scope() as session:
        job = session.exec(select(Job).where(Job.id == jid)).first()
        scenes = session.exec(select(Scene).where(Scene.project_id == pid)).all()
        if job:
            print("job", job.status, job.progress, (job.message or "")[:120])
        print("scenes", len(scenes))

        # cleanup records created by this script
        for sc in scenes:
            session.delete(sc)
        if job:
            session.delete(job)
        proj = session.exec(select(Project).where(Project.id == pid)).first()
        if proj:
            session.delete(proj)

    print("cleanup ok")


if __name__ == "__main__":
    main()
