from sqlmodel import Session
from threading import Lock, Thread
from time import monotonic


PROJECTION_REFRESH_KEY = "projection_refresh_project_ids"
REBUILD_ALL_MIN_INTERVAL_S = 30.0

_rebuild_all_lock = Lock()
_rebuild_all_in_progress = False
_rebuild_all_last_started_at = 0.0


def schedule_project_refresh(session: Session, project_id: int | None) -> None:
    pid = int(project_id or 0)
    if pid <= 0:
        return
    pending = session.info.setdefault(PROJECTION_REFRESH_KEY, set())
    if isinstance(pending, set):
        pending.add(pid)


def pop_scheduled_project_refreshes(session: Session) -> list[int]:
    pending = session.info.pop(PROJECTION_REFRESH_KEY, set())
    if not isinstance(pending, set):
        return []
    return sorted(int(pid) for pid in pending if int(pid) > 0)


def run_project_refreshes(project_ids: list[int]) -> None:
    if not project_ids:
        return
    try:
        from app.tasks_projection import refresh_feed_projection_batch

        refresh_feed_projection_batch.schedule(args=(project_ids,), delay=0)
        return
    except Exception:
        from app.application.feed import refresh_project_projections

        refresh_project_projections(project_ids)


def _mark_rebuild_all_finished() -> None:
    global _rebuild_all_in_progress
    with _rebuild_all_lock:
        _rebuild_all_in_progress = False


def _run_rebuild_all_inline() -> None:
    try:
        from app.application.feed import rebuild_all_projections

        rebuild_all_projections()
    finally:
        _mark_rebuild_all_finished()


def schedule_rebuild_all_projections_once() -> bool:
    """Schedule a full projection rebuild without blocking the request path."""
    global _rebuild_all_in_progress, _rebuild_all_last_started_at
    now = monotonic()
    with _rebuild_all_lock:
        if _rebuild_all_in_progress:
            return False
        if now - _rebuild_all_last_started_at < REBUILD_ALL_MIN_INTERVAL_S:
            return False
        _rebuild_all_in_progress = True
        _rebuild_all_last_started_at = now

    try:
        from app.tasks_projection import rebuild_feed_projections

        rebuild_feed_projections.schedule(delay=0)
        return True
    except Exception:
        try:
            Thread(target=_run_rebuild_all_inline, name="feed-projection-rebuild", daemon=True).start()
            return True
        except Exception:
            _mark_rebuild_all_finished()
            return False
