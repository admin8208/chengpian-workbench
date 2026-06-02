from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass, field


@dataclass
class FeedEvent:
    kind: str
    project_ids: list[int] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class FeedEventBus:
    def __init__(self) -> None:
        self._subscribers: list[queue.Queue[FeedEvent]] = []
        self._lock = threading.Lock()

    def publish(self, event: FeedEvent) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
        for q in subscribers:
            try:
                q.put_nowait(event)
            except Exception:
                continue

    def subscribe(self) -> queue.Queue[FeedEvent]:
        q: queue.Queue[FeedEvent] = queue.Queue(maxsize=100)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue[FeedEvent]) -> None:
        with self._lock:
            self._subscribers = [item for item in self._subscribers if item is not q]


feed_event_bus = FeedEventBus()


def publish_feed_event(kind: str, project_ids: list[int] | None = None) -> None:
    normalized = sorted({int(pid) for pid in (project_ids or []) if int(pid) > 0})
    feed_event_bus.publish(FeedEvent(kind=str(kind or 'refresh'), project_ids=normalized))


def encode_sse_event(event: FeedEvent) -> str:
    payload = {
        'kind': event.kind,
        'project_ids': event.project_ids,
        'created_at': event.created_at,
    }
    return f"event: feed\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"
