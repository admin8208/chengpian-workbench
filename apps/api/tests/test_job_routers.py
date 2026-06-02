import unittest
from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.application.jobs.service import cancel_job_api, delete_job_api, pause_job_api, resume_job_api, retry_job_api
from app.main import app


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None


class _Session:
    def __init__(self, first=None):
        self.first_obj = first
        self.added = []

    def exec(self, _query):
        return _Rows([self.first_obj] if self.first_obj is not None else [])

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.added.append(("deleted", obj))


class JobRouterTests(unittest.TestCase):
    def _job_out_dict(self, job_id: int, *, status: str = "queued"):
        now = datetime.now(UTC)
        return {
            "id": job_id,
            "kind": "render",
            "project_id": 4,
            "status": status,
            "progress": 0,
            "message": "",
            "payload_json": "{}",
            "created_at": now,
            "updated_at": now,
        }

    def test_cancel_job_rejects_terminal_status(self):
        session = _Session(first=SimpleNamespace(id=7, status="done"))
        with patch("app.application.jobs.service.session_scope", return_value=nullcontext(session)):
            with self.assertRaises(HTTPException) as ctx:
                cancel_job_api(7)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("不支持取消", str(ctx.exception.detail))

    def test_pause_job_rejects_non_active_status(self):
        session = _Session(first=SimpleNamespace(id=8, status="paused"))
        with patch("app.application.jobs.service.session_scope", return_value=nullcontext(session)):
            with self.assertRaises(HTTPException) as ctx:
                pause_job_api(8)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("不支持暂停", str(ctx.exception.detail))

    def test_resume_job_rejects_non_paused_status(self):
        session = _Session(first=SimpleNamespace(id=9, status="running"))
        with patch("app.application.jobs.service.session_scope", return_value=nullcontext(session)):
            with self.assertRaises(HTTPException) as ctx:
                resume_job_api(9)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("不支持继续", str(ctx.exception.detail))

    def test_cancel_job_cleans_outputs_before_requesting_cancel(self):
        job = SimpleNamespace(id=10, status="running", kind="render", project_id=3)
        session = _Session(first=job)
        with patch("app.application.jobs.service.session_scope", return_value=nullcontext(session)), patch("app.application.jobs.service.delete_outputs_for_job") as delete_outputs, patch(
            "app.application.jobs.service.request_job_cancel", return_value=True
        ) as request_cancel, patch("app.application.jobs.service.job_out", return_value=SimpleNamespace(id=10, status="running", cancel_requested=True)), patch(
            "app.application.jobs.service._refresh_projection"
        ):
            out = cancel_job_api(10)
        delete_outputs.assert_called_once_with(session, job)
        request_cancel.assert_called_once_with(10, source="user", reason="用户取消任务")
        self.assertTrue(out.cancel_requested)

    def test_retry_job_cleans_outputs_before_requeue(self):
        job = SimpleNamespace(id=11, status="failed", kind="render", project_id=4, payload_json='{"current_stage":"tts","current_substage":"generate_voice","render_substage":"mux_prepare"}', root_job_id=11, retry_seq=0)
        session = _Session(first=job)
        created_job = self._job_out_dict(12, status="queued")
        with patch("app.application.jobs.service.session_scope", return_value=nullcontext(session)), patch("app.application.jobs.service.delete_outputs_for_job") as delete_outputs, patch(
            "app.application.jobs.service.enqueue_project_job", return_value=created_job
        ) as enqueue_job, patch("app.application.jobs.service.render_video.schedule", return_value=SimpleNamespace(id="task-1")), patch("app.application.jobs.service.job_out", return_value=self._job_out_dict(12, status="queued")), patch(
            "app.application.jobs.service._refresh_projection"
        ):
            out = retry_job_api(11)
        delete_outputs.assert_called_once_with(session, job)
        self.assertEqual(enqueue_job.call_args.kwargs["payload"], {"render_substage": "mux_prepare"})
        self.assertEqual(out.job.id, 12)

    def test_retry_autopilot_normalizes_legacy_resume_stage(self):
        payload_json = '{"resume_from_stage":"visual_resolve","current_stage":"visual_resolve"}'
        job = SimpleNamespace(id=21, status="failed", kind="autopilot", project_id=4, payload_json=payload_json, root_job_id=21, retry_seq=0)
        session = _Session(first=job)
        project = SimpleNamespace(id=4, current_pipeline_run_id=None)
        created_job = self._job_out_dict(22, status="queued")
        created_job["kind"] = "autopilot"
        with patch("app.application.jobs.service.session_scope", side_effect=[nullcontext(session), nullcontext(_Session(first=project))]), patch(
            "app.application.jobs.service.delete_outputs_for_job"
        ) as delete_outputs, patch("app.application.jobs.service.latest_autopilot_job", return_value=None), patch(
            "app.application.jobs.service.enqueue_project_job", return_value=created_job
        ) as enqueue_job:
            out = retry_job_api(21)
        delete_outputs.assert_called_once_with(session, job)
        self.assertEqual(out.job.id, 22)
        self.assertEqual(enqueue_job.call_args.kwargs["payload"]["resume_from_stage"], "media")
        self.assertEqual(enqueue_job.call_args.kwargs["payload"]["current_stage"], "media")

    def test_retry_autopilot_clears_stale_error_meta(self):
        payload_json = '{"resume_from_stage":"tts","current_stage":"tts","error_code":"tts_unavailable","blocking_component":"tts","recommended_action":"go_settings_tts","recoverable":true}'
        job = SimpleNamespace(id=23, status="failed", kind="autopilot", project_id=4, payload_json=payload_json, root_job_id=23, retry_seq=0)
        session = _Session(first=job)
        project = SimpleNamespace(id=4, current_pipeline_run_id=None)
        created_job = self._job_out_dict(24, status="queued")
        created_job["kind"] = "autopilot"
        with patch("app.application.jobs.service.session_scope", side_effect=[nullcontext(session), nullcontext(_Session(first=project))]), patch(
            "app.application.jobs.service.delete_outputs_for_job"
        ) as delete_outputs, patch("app.application.jobs.service.latest_autopilot_job", return_value=None), patch(
            "app.application.jobs.service.enqueue_project_job", return_value=created_job
        ) as enqueue_job:
            out = retry_job_api(23)
        delete_outputs.assert_called_once_with(session, job)
        self.assertEqual(out.job.id, 24)
        self.assertNotIn("error_code", enqueue_job.call_args.kwargs["payload"])
        self.assertNotIn("blocking_component", enqueue_job.call_args.kwargs["payload"])
        self.assertNotIn("recommended_action", enqueue_job.call_args.kwargs["payload"])
        self.assertNotIn("recoverable", enqueue_job.call_args.kwargs["payload"])

    def test_retry_script_prepare_requeues_prepare_job(self):
        job = SimpleNamespace(id=25, status="failed", kind="script_prepare", project_id=6, payload_json='{"current_stage":"baseline_prepare"}', root_job_id=25, retry_seq=0)
        session = _Session(first=job)
        created_job = self._job_out_dict(26, status="queued")
        created_job["kind"] = "script_prepare"
        with patch("app.application.jobs.service.session_scope", return_value=nullcontext(session)), patch(
            "app.application.jobs.service.delete_outputs_for_job"
        ) as delete_outputs, patch(
            "app.application.jobs.service.enqueue_project_job", return_value=created_job
        ) as enqueue_job, patch("app.application.jobs.service.prepare_project_script.schedule", return_value=SimpleNamespace(id="task-prepare")), patch(
            "app.application.jobs.service.job_out", return_value=self._job_out_dict(26, status="queued")
        ), patch(
            "app.application.jobs.service._refresh_projection"
        ):
            out = retry_job_api(25)
        delete_outputs.assert_called_once_with(session, job)
        self.assertEqual(enqueue_job.call_args.kwargs["payload"]["current_stage"], "baseline_prepare")
        self.assertEqual(out.job.id, 26)

    def test_delete_job_rejects_active_status(self):
        session = _Session(first=SimpleNamespace(id=13, status="running"))
        with patch("app.application.jobs.service.session_scope", return_value=nullcontext(session)):
            with self.assertRaises(HTTPException) as ctx:
                delete_job_api(13)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("不能直接删除", str(ctx.exception.detail))

    def test_delete_job_removes_terminal_job(self):
        job = SimpleNamespace(id=14, status="failed", kind="render", project_id=3)
        session = _Session(first=job)
        with patch("app.application.jobs.service.session_scope", return_value=nullcontext(session)), patch("app.application.jobs.service.delete_outputs_for_job") as delete_outputs, patch(
            "app.application.jobs.service._refresh_projection"
        ):
            out = delete_job_api(14)
        delete_outputs.assert_called_once_with(session, job)
        self.assertEqual(out.ok, True)
        self.assertIn(("deleted", job), session.added)

    def test_delete_job_delete_route_maps_to_delete_api(self):
        client = TestClient(app)
        with patch("app.api.auth_web.auth_is_configured", return_value=True), patch(
            "app.api.auth_web.get_authenticated_principal", return_value={"username": "admin", "is_admin": True}
        ), patch("app.api.job.delete_job_api", return_value=SimpleNamespace(ok=True)) as delete_api:
            res = client.delete("/api/jobs/14")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"ok": True})
        delete_api.assert_called_once_with(14)


if __name__ == "__main__":
    unittest.main()
