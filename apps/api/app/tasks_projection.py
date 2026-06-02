from app.application.feed import refresh_project_projections
from app.application.feed import rebuild_all_projections
from app.feed_events import publish_feed_event
from app.huey_app import huey
from app.projection_refresh import _mark_rebuild_all_finished


@huey.task()
def refresh_feed_projection_batch(project_ids: list[int]) -> None:
    normalized = sorted({int(pid) for pid in (project_ids or []) if int(pid) > 0})
    if not normalized:
        return
    refresh_project_projections(normalized)
    publish_feed_event('projection_refreshed', normalized)


@huey.task()
def rebuild_feed_projections() -> None:
    try:
        rebuild_all_projections()
        publish_feed_event('projection_rebuilt', [])
    finally:
        _mark_rebuild_all_finished()
