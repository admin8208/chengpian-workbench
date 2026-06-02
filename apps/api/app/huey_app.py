
import json
from threading import Lock

from huey import RedisHuey, crontab
from sqlalchemy import text
from sqlmodel import select

from app.db import engine
from app.db import session_scope
from app.models import Job
from app.modules.pipeline.state import normalize_autopilot_stage
from app.settings import settings


# Redis-backed queue is used for production-grade cross-process task dispatch.
# PostgreSQL remains the business database; Redis only stores transient Huey
# queue/result data.
huey = RedisHuey("chengpian", url=settings.redis_url, blocking=True, read_timeout=1)


# 渲染任务队列管理
class RenderQueueManager:
    def __init__(self):
        self.max_concurrent_renders = 2
        self._slot_guard = Lock()
        self._held_slots: dict[int, tuple[int, object]] = {}

    def _slot_lock_key(self, slot_index: int) -> int:
        return 924200 + int(slot_index)

    def _job_counts_as_render(self, job: Job) -> bool:
        kind = str(getattr(job, "kind", "") or "").strip().lower()
        if kind == "render":
            return True
        if kind != "autopilot":
            return False
        try:
            payload = json.loads(getattr(job, "payload_json", "{}") or "{}")
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        stage = normalize_autopilot_stage(payload.get("current_stage") or payload.get("last_failed_stage"))
        return stage == "render"

    def get_running_render_count(self, *, exclude_job_id: int | None = None) -> int:
        count = 0
        with session_scope() as session:
            rows = session.exec(select(Job).where(Job.status == "running")).all()
            for job in rows:
                try:
                    if exclude_job_id is not None and int(getattr(job, "id", 0) or 0) == int(exclude_job_id):
                        continue
                except Exception:
                    pass
                if self._job_counts_as_render(job):
                    count += 1
        return count

    def can_start_render(self, *, exclude_job_id: int | None = None) -> bool:
        return self.get_running_render_count(exclude_job_id=exclude_job_id) < self.max_concurrent_renders

    def acquire_render_slot(self, *, job_id: int) -> bool:
        target_job_id = int(job_id)
        with self._slot_guard:
            if target_job_id in self._held_slots:
                return True
        for slot_index in range(1, int(self.max_concurrent_renders) + 1):
            conn = engine.connect()
            try:
                locked = bool(conn.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": self._slot_lock_key(slot_index)}).scalar())
                conn.commit()
                if not locked:
                    conn.close()
                    continue
                with self._slot_guard:
                    if target_job_id in self._held_slots:
                        conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": self._slot_lock_key(slot_index)})
                        conn.commit()
                        conn.close()
                        return True
                    self._held_slots[target_job_id] = (slot_index, conn)
                return True
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
                raise
        return False

    def release_render_slot(self, *, job_id: int) -> None:
        target_job_id = int(job_id)
        with self._slot_guard:
            held = self._held_slots.pop(target_job_id, None)
        if not held:
            return
        slot_index, conn = held
        try:
            conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": self._slot_lock_key(slot_index)})
            conn.commit()
        finally:
            conn.close()


# 创建全局渲染队列管理器
render_queue_manager = RenderQueueManager()
