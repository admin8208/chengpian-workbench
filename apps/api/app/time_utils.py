from datetime import UTC, datetime


def now_utc() -> datetime:
    return datetime.now(UTC)


def utc_iso_z(dt: datetime | None = None) -> str:
    cur = dt or now_utc()
    return cur.isoformat().replace("+00:00", "Z")
