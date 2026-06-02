from __future__ import annotations

from pathlib import Path

from app.settings import settings


RUNTIME_DIRS = [
    settings.data_dir,
    settings.assets_dir,
    settings.exports_dir,
    settings.huey_storage_dir,
    settings.assets_dir / "audio",
    settings.assets_dir / "subtitles",
    settings.assets_dir / "library",
    settings.assets_dir / "tts_cache",
]


def _assert_writable_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".write_test"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink(missing_ok=True)


def ensure_runtime_storage() -> None:
    for p in RUNTIME_DIRS:
        _assert_writable_dir(p)
