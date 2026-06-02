from __future__ import annotations

import sys
import threading
import time

from huey.bin.huey_consumer import consumer_main

from app.db import init_db
from app.jobs import recover_abandoned_jobs, touch_worker_heartbeat
from app.logging_setup import configure_safe_logging
from app.preflight import run_preflight
from app.runtime_encoding import configure_utf8_stdio
from app.runtime_guard import enforce_non_root_runtime
from app.settings import settings


def _start_worker_heartbeat() -> None:
    def _beat() -> None:
        while True:
            touch_worker_heartbeat()
            time.sleep(15)

    thread = threading.Thread(target=_beat, name="worker-heartbeat", daemon=True)
    thread.start()


if __name__ == "__main__":
    configure_utf8_stdio()
    configure_safe_logging()
    enforce_non_root_runtime(data_dir=settings.data_dir, role="Worker")
    for line in run_preflight(require_web_dist=False, role="worker"):
        print(line)
    # Ensure business schema/migrations are applied.
    init_db()
    recovered = recover_abandoned_jobs()
    if recovered:
        print(f"[worker] recovered abandoned jobs: {recovered}")
    _start_worker_heartbeat()
    # Equivalent to: huey_consumer.py app.worker.huey
    sys.argv = [
        sys.argv[0],
        "app.worker.huey",
        "--workers",
        str(int(settings.worker_count or 1)),
    ]
    consumer_main()
