import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.job_health import ensure_job_dispatch_ready
from app.schemas import HealthComponentOut


class JobHealthTests(unittest.TestCase):
    def test_dispatch_ready_reconciles_stale_jobs_before_checks(self):
        with patch("app.job_health.reconcile_stale_jobs_before_dispatch") as reconcile, patch(
            "app.job_health.check_huey_queue",
            return_value=HealthComponentOut(ok=True, status="正常"),
        ), patch(
            "app.job_health.check_worker",
            return_value=HealthComponentOut(ok=True, status="在线"),
        ):
            ensure_job_dispatch_ready()
        reconcile.assert_called_once()

    def test_dispatch_ready_raises_when_queue_unavailable(self):
        with patch(
            "app.job_health.check_huey_queue",
            return_value=HealthComponentOut(ok=False, status="错误", detail="redis down"),
        ), patch(
            "app.job_health.check_worker",
            return_value=HealthComponentOut(ok=True, status="在线"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                ensure_job_dispatch_ready()
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("Redis/Huey", str(ctx.exception.detail))

    def test_dispatch_ready_raises_when_worker_offline(self):
        with patch(
            "app.job_health.check_huey_queue",
            return_value=HealthComponentOut(ok=True, status="正常"),
        ), patch(
            "app.job_health.check_worker",
            return_value=HealthComponentOut(ok=False, status="离线", detail="no heartbeat", hint="check service"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                ensure_job_dispatch_ready()
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("Worker 未就绪", str(ctx.exception.detail))


if __name__ == "__main__":
    unittest.main()
