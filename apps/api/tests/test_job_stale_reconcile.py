import unittest
from contextlib import nullcontext
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from app.job_control import finalize_cancelled_job_if_stale_in_session, job_lease_is_stale
from app.job_recovery import recover_abandoned_jobs
from app.time_utils import now_utc


class _Session:
    def __init__(self, rows):
        self.rows = rows
        self.added = []

    def exec(self, _query):
        class _Rows:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return list(self._rows)

            def first(self):
                return self._rows[0] if self._rows else None

        return _Rows(self.rows)

    def add(self, obj):
        self.added.append(obj)


class JobStaleRecoveryTests(unittest.TestCase):
    def test_job_lease_is_stale_when_worker_pid_missing(self):
        touched_at = now_utc() - timedelta(seconds=5)
        job = SimpleNamespace(
            status="running",
            worker_pid=999999,
            worker_heartbeat_at=touched_at,
            updated_at=touched_at,
            created_at=touched_at,
        )
        self.assertTrue(job_lease_is_stale(job, now=now_utc()))

    def test_finalize_cancelled_job_allows_stale_lease_with_residual_worker_fields(self):
        touched_at = now_utc() - timedelta(minutes=30)
        job = SimpleNamespace(
            id=104,
            kind="autopilot",
            project_id=0,
            status="running",
            progress=40,
            message="处理中",
            cancel_requested=True,
            worker_id="worker-1",
            worker_pid=999999,
            worker_heartbeat_at=touched_at,
            created_at=touched_at,
            updated_at=touched_at,
        )
        session = _Session([job])
        changed = finalize_cancelled_job_if_stale_in_session(session, 104)
        self.assertTrue(changed)
        self.assertEqual(job.status, "cancelled")
        self.assertEqual(job.progress, 100)
        self.assertEqual(job.worker_id, "")
        self.assertEqual(job.worker_pid, 0)

    def test_worker_recovery_marks_stale_running_job_failed(self):
        touched_at = now_utc() - timedelta(minutes=30)
        job = SimpleNamespace(
            id=102,
            kind="autopilot",
            project_id=8,
            status="running",
            progress=40,
            message="处理中",
            worker_id="worker-1",
            worker_pid=999999,
            worker_heartbeat_at=touched_at,
            created_at=touched_at,
            updated_at=touched_at,
        )
        session = _Session([job])

        with patch("app.job_recovery.session_scope", return_value=nullcontext(session)):
            changed = recover_abandoned_jobs(stale_minutes=10)

        self.assertEqual(changed, 1)
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.progress, 100)
        self.assertEqual(job.worker_id, "")
        self.assertIn("worker 心跳超时", job.message)

    def test_worker_recovery_marks_stale_non_project_job_failed(self):
        touched_at = now_utc() - timedelta(minutes=30)
        job = SimpleNamespace(
            id=103,
            kind="tts_offline_install",
            project_id=0,
            status="running",
            progress=20,
            message="备份中",
            worker_id="worker-2",
            worker_pid=999999,
            worker_heartbeat_at=touched_at,
            created_at=touched_at,
            updated_at=touched_at,
        )
        session = _Session([job])

        with patch("app.job_recovery.session_scope", return_value=nullcontext(session)):
            changed = recover_abandoned_jobs(stale_minutes=10)

        self.assertEqual(changed, 1)
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.progress, 100)
        self.assertEqual(job.worker_id, "")
        self.assertIn("worker 心跳超时", job.message)


if __name__ == "__main__":
    unittest.main()
