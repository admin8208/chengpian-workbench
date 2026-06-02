from __future__ import annotations

import os

import uvicorn

from app.logging_setup import configure_safe_logging
from app.preflight import run_preflight
from app.runtime_encoding import configure_utf8_stdio
from app.runtime_guard import enforce_non_root_runtime
from app.settings import settings


if __name__ == "__main__":
    configure_utf8_stdio()
    configure_safe_logging()
    enforce_non_root_runtime(data_dir=settings.data_dir, role="API")
    for line in run_preflight(require_web_dist=True, role="api"):
        print(line)
    reload = os.environ.get("CHENGPIAN_RELOAD", "1").strip().lower() not in ("0", "false", "no")
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=reload,
        log_level="info",
    )
