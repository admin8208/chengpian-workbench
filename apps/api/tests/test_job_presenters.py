import unittest
from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from app.services.job_presenters import job_out


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None


class _Session:
    def __init__(self, first):
        self.first_obj = first

    def exec(self, _query):
        return _Rows([self.first_obj] if self.first_obj is not None else [])


class JobPresenterTests(unittest.TestCase):
    def test_job_out_handles_system_job_without_project(self):
        now = datetime.now(UTC)
        job = SimpleNamespace(
            id=101,
            kind="tts_offline_install_all_compatible",
            project_id=0,
            parent_job_id=None,
            root_job_id=None,
            retry_seq=0,
            status="queued",
            progress=0,
            message="排队中",
            payload_json="{}",
            cancel_requested=False,
            pause_requested=False,
            cancel_source="",
            cancel_reason="",
            worker_id="",
            worker_pid=0,
            worker_started_at=None,
            worker_heartbeat_at=None,
            created_at=now,
            updated_at=now,
        )
        session = _Session(job)

        with patch("app.services.job_presenters.session_scope", return_value=nullcontext(session)), patch(
            "app.services.job_presenters.get_job_payload", return_value={}
        ), patch("app.services.job_presenters.get_pipeline_run") as get_pipeline_run:
            out = job_out(101)

        self.assertEqual(out.id, 101)
        self.assertEqual(out.project_id, 0)
        self.assertIsNone(out.project_title)
        self.assertIsNone(out.project_workflow)
        get_pipeline_run.assert_not_called()

    def test_job_out_treats_render_job_as_render_stage_only(self):
        now = datetime.now(UTC)
        job = SimpleNamespace(
            id=102,
            kind="render",
            project_id=7,
            parent_job_id=None,
            root_job_id=None,
            retry_seq=0,
            status="running",
            progress=50,
            message="正在渲染成片",
            payload_json='{"current_stage":"tts","current_substage":"generate_voice","render_substage":"mux_prepare"}',
            cancel_requested=False,
            pause_requested=False,
            cancel_source="",
            cancel_reason="",
            worker_id="",
            worker_pid=0,
            worker_started_at=None,
            worker_heartbeat_at=None,
            created_at=now,
            updated_at=now,
        )
        project = SimpleNamespace(id=7, title="测试项目", workflow="mix", current_pipeline_run_id=None)

        class _SessionWithProject:
            def __init__(self):
                self.calls = 0

            def exec(self, _query):
                self.calls += 1
                return _Rows([job] if self.calls == 1 else [project])

        session = _SessionWithProject()

        with patch("app.services.job_presenters.session_scope", return_value=nullcontext(session)), patch(
            "app.services.job_presenters.get_job_payload",
            return_value={"current_stage": "tts", "current_substage": "generate_voice", "render_substage": "mux_prepare"},
        ), patch("app.services.job_presenters.get_pipeline_run", return_value=None):
            out = job_out(102)

        self.assertEqual(out.current_stage, "render")
        self.assertIsNone(out.current_substage)
        self.assertEqual(out.render_substage, "mux_prepare")

    def test_job_out_hides_error_meta_for_running_jobs(self):
        now = datetime.now(UTC)
        job = SimpleNamespace(
            id=103,
            kind="autopilot",
            project_id=7,
            parent_job_id=None,
            root_job_id=None,
            retry_seq=0,
            status="running",
            progress=50,
            message="正在生成配音",
            payload_json='{"error_code":"tts_unavailable","blocking_component":"tts","recommended_action":"go_settings_tts","recoverable":true}',
            cancel_requested=False,
            pause_requested=False,
            cancel_source="",
            cancel_reason="",
            worker_id="",
            worker_pid=0,
            worker_started_at=None,
            worker_heartbeat_at=None,
            created_at=now,
            updated_at=now,
        )
        project = SimpleNamespace(id=7, title="测试项目", workflow="mix", current_pipeline_run_id=None)

        class _SessionWithProject:
            def __init__(self):
                self.calls = 0

            def exec(self, _query):
                self.calls += 1
                return _Rows([job] if self.calls == 1 else [project])

        session = _SessionWithProject()

        with patch("app.services.job_presenters.session_scope", return_value=nullcontext(session)), patch(
            "app.services.job_presenters.get_job_payload",
            return_value={"error_code": "tts_unavailable", "blocking_component": "tts", "recommended_action": "go_settings_tts", "recoverable": True},
        ), patch("app.services.job_presenters.get_pipeline_run", return_value=None):
            out = job_out(103)

        self.assertEqual(out.id, 103)
        self.assertIsNone(out.error_code)
        self.assertIsNone(out.blocking_component)
        self.assertIsNone(out.recommended_action)
        self.assertIsNone(out.recoverable)


if __name__ == "__main__":
    unittest.main()
