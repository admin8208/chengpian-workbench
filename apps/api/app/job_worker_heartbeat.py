import json
from pathlib import Path

from app.settings import settings
from app.time_utils import now_utc

WORKER_HEARTBEAT_STALE_SECONDS = 90


def worker_heartbeat_path() -> Path:
    return settings.huey_storage_dir / "worker_heartbeat.json"


def touch_worker_heartbeat() -> None:
    try:
        heartbeat = worker_heartbeat_path()
        heartbeat.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"ts": now_utc().timestamp()}, ensure_ascii=True)
        heartbeat.write_text(payload, encoding="utf-8")
    except Exception:
        pass


def worker_heartbeat_age_seconds() -> int | None:
    try:
        heartbeat = worker_heartbeat_path()
        if not heartbeat.exists() or not heartbeat.is_file():
            return None
        raw = json.loads(heartbeat.read_text(encoding="utf-8") or "{}")
        ts = float(raw.get("ts") or 0)
        if ts <= 0:
            return None
        return max(0, int(now_utc().timestamp() - ts))
    except Exception:
        return None


def worker_heartbeat_alive(*, stale_seconds: int = WORKER_HEARTBEAT_STALE_SECONDS) -> bool:
    age = worker_heartbeat_age_seconds()
    if age is None:
        return False
    return age <= max(15, int(stale_seconds or WORKER_HEARTBEAT_STALE_SECONDS))
