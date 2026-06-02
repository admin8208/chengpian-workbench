import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.job_dispatcher import enqueue_project_job


class JobDispatcherTests(unittest.TestCase):
    def _job_out_stub(self, job_id: int):
        return SimpleNamespace(id=job_id, status="queued")

    def test_enqueue_project_job_marks_failed_when_schedule_raises(self):
        job = SimpleNamespace(id=17)
        with patch("app.job_dispatcher.ensure_job_dispatch_ready"), patch("app.job_dispatcher.create_job", return_value=job), patch(
            "app.job_dispatcher.mark_job_enqueue_failed"
        ) as mark_failed, patch("app.job_dispatcher.job_out", side_effect=self._job_out_stub):
            with self.assertRaises(HTTPException) as ctx:
                enqueue_project_job(
                    kind="render",
                    project_id=7,
                    message="排队中",
                    payload={"project_id": 7},
                    enqueue=lambda _job_id: (_ for _ in ()).throw(RuntimeError("redis down")),
                    enqueue_error_message="渲染任务入队失败，请检查后台任务服务",
                )
        self.assertEqual(ctx.exception.status_code, 500)
        mark_failed.assert_called_once()
        self.assertIn("渲染任务入队失败", str(ctx.exception.detail))

    def test_enqueue_project_job_marks_failed_when_enqueued_check_fails(self):
        job = SimpleNamespace(id=18)
        with patch("app.job_dispatcher.ensure_job_dispatch_ready"), patch("app.job_dispatcher.create_job", return_value=job), patch(
            "app.job_dispatcher.ensure_enqueued", side_effect=RuntimeError("worker unavailable")
        ), patch("app.job_dispatcher.mark_job_enqueue_failed") as mark_failed, patch(
            "app.job_dispatcher.job_out", side_effect=self._job_out_stub
        ):
            with self.assertRaises(HTTPException) as ctx:
                enqueue_project_job(
                    kind="render",
                    project_id=7,
                    message="排队中",
                    payload={"project_id": 7},
                    enqueue=lambda _job_id: SimpleNamespace(id="task-1"),
                    enqueue_error_message="渲染任务入队失败，请检查后台任务服务",
                )
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(str(ctx.exception.detail), "worker unavailable")
        mark_failed.assert_called_once_with(18, message="worker unavailable")

    def test_enqueue_project_job_checks_dispatch_health_before_creating_job(self):
        with patch("app.job_dispatcher.ensure_job_dispatch_ready", side_effect=HTTPException(status_code=503, detail="worker offline")), patch(
            "app.job_dispatcher.create_job"
        ) as create_job:
            with self.assertRaises(HTTPException) as ctx:
                enqueue_project_job(
                    kind="render",
                    project_id=7,
                    message="排队中",
                    payload={"project_id": 7},
                    enqueue=lambda _job_id: SimpleNamespace(id="task-1"),
                    enqueue_error_message="渲染任务入队失败，请检查后台任务服务",
                )
        self.assertEqual(ctx.exception.status_code, 503)
        create_job.assert_not_called()


if __name__ == "__main__":
    unittest.main()
