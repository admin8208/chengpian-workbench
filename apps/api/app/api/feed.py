import time
import anyio
from queue import Empty

from fastapi import APIRouter, Query
from fastapi import Request
from fastapi.responses import StreamingResponse

from app.application.feed import (
    get_job_center_feed_from_projection,
    get_project_center_feed_from_projection,
)
from app.feed_events import encode_sse_event, feed_event_bus
from app.projection_refresh import schedule_rebuild_all_projections_once
from app.schemas import JobCenterFeedOut, JobCenterStatsOut, ProjectCenterFeedOut, ProjectCenterStatsOut
from app.time_utils import now_utc

router = APIRouter(tags=["feed"])


@router.get("/api/project-center/feed", response_model=ProjectCenterFeedOut)
def project_center_feed(limit: int = Query(200, ge=1, le=500), cursor: str = Query('')):
    feed = get_project_center_feed_from_projection(limit=limit, cursor=cursor)
    if feed.items:
        return feed
    schedule_rebuild_all_projections_once()
    return ProjectCenterFeedOut(stats=ProjectCenterStatsOut(all=0, running=0, failed=0, final_ready=0), items=[], server_time=now_utc(), rebuilding=True)


@router.get("/api/job-center/feed", response_model=JobCenterFeedOut)
def job_center_feed(
    limit: int = Query(200, ge=1, le=500),
    scope: str = Query("project"),
    status: str = Query("all"),
    project_id: int = Query(0, ge=0),
    cursor: str = Query(''),
):
    feed = get_job_center_feed_from_projection(limit=limit, scope=scope, status=status, project_id=project_id, cursor=cursor)
    if feed.items:
        return feed
    schedule_rebuild_all_projections_once()
    return JobCenterFeedOut(stats=JobCenterStatsOut(all=0, active=0, failed=0, done=0, cancelled=0), items=[], server_time=now_utc(), rebuilding=True)


@router.get('/api/feed/events')
async def feed_events(request: Request):
    subscriber = feed_event_bus.subscribe()

    async def stream():
        try:
            yield 'event: ready\ndata: {"ok":true}\n\n'
            while True:
                if hasattr(request, 'is_disconnected'):
                    try:
                        if await request.is_disconnected():
                            break
                    except Exception:
                        pass
                try:
                    event = await anyio.to_thread.run_sync(subscriber.get, True, 15)
                    yield encode_sse_event(event)
                except Empty:
                    yield f"event: ping\ndata: {{\"ts\":{time.time():.3f}}}\n\n"
        finally:
            feed_event_bus.unsubscribe(subscriber)

    return StreamingResponse(stream(), media_type='text/event-stream')
