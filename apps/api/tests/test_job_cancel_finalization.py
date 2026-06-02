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

    def all(self):
        return list(self._rows)


class _Session:
    def __init__(self, job, project, run):
        self.job = job
        self.project = project
        self.run = run
        self.added = []

    def exec(self, query):
        text = str(query)
        if "FROM job" in text:
            return _Rows([self.job])
        if "FROM project" in text:
            return _Rows([self.project])
        if "FROM pipelinerun" in text:
            return _Rows([self.run])
        return _Rows([])

    def add(self, obj):
        self.added.append(obj)


class JobCancelFinalizationTests(unittest.TestCase):
    def test_job_out_finalizes_cancel_requested_running_job_without_worker(self):
        now = datetime.now(UTC)
        job = SimpleNamespace(
            id=9,
            kind="autopilot",
            project_id=2,
            parent_job_id=None,
            root_job_id=9,
            retry_seq=0,
            status="running",
            progress=85,
            message="已取消",
            payload_json='{"pipeline_run_id": 7, "current_stage": "render", "render_substage": "silent_track_prepare"}',
            cancel_requested=True,
            pause_requested=False,
            cancel_source="user",
            cancel_reason="用户取消任务",
            worker_id="",
            worker_pid=0,
            worker_started_at=now,
            worker_heartbeat_at=None,
            created_at=now,
            updated_at=now,
        )
        project = SimpleNamespace(id=2, title="测试项目", workflow="mix", current_pipeline_run_id=7)
        run = SimpleNamespace(id=7, project_id=2, status="running", current_stage="render_finalize", current_substage="", resume_from_stage="", error_code="", error_detail="", created_at=now, updated_at=now)
        session = _Session(job, project, run)

        with patch("app.services.job_presenters.session_scope", return_value=nullcontext(session)), patch(
            "app.services.job_presenters.get_job_payload", return_value={"pipeline_run_id": 7, "current_stage": "render", "render_substage": "silent_track_prepare"}
        ):
            out = job_out(9)

        self.assertEqual(out.status, "cancelled")
        self.assertEqual(job.status, "cancelled")
        self.assertEqual(run.status, "cancelled")


if __name__ == "__main__":
    unittest.main()
