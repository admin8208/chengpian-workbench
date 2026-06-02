import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from app.tasks_entries import autofill_media

from app.tasks_autopilot import run_autopilot_media_stage


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _Session:
    def __init__(self, queue=None):
        self.queue = list(queue or [])

    def exec(self, _query):
        rows = self.queue.pop(0) if self.queue else []
        return _Rows(rows)


class AutopilotAiMediaStageTests(unittest.TestCase):
    def test_autofill_media_keep_running_marks_outer_job_running(self):
        updates = []

        with patch("app.tasks_media_facade.update_job", side_effect=lambda job_id, **kwargs: updates.append((job_id, dict(kwargs)))), patch(
            "app.tasks_media_facade.is_job_cancelled", return_value=False
        ), patch("app.tasks_media_facade.wait_if_job_paused"), patch(
            "app.tasks_media_facade.session_scope", return_value=nullcontext(_Session(queue=[[SimpleNamespace(id=4, channel_key="career", title="t", render_config=lambda: {"aspect": "landscape"})], []]))
        ), patch("app.tasks_media_facade.supported_providers", return_value=[]):
            autofill_media.call_local(21, 4, outer_job_id=99, keep_running=True)

        self.assertTrue(any(job_id == 99 and kwargs.get("status") == "running" for job_id, kwargs in updates))

    def test_ai_media_stage_uses_incremental_generation(self):
        project = SimpleNamespace(id=1)
        scenes = [SimpleNamespace(idx=1, image_asset_id=11), SimpleNamespace(idx=2, image_asset_id=12)]
        session1 = _Session(queue=[[project]])
        session2 = _Session(queue=[scenes])

        with patch("app.tasks_autopilot.session_scope", side_effect=[nullcontext(session1), nullcontext(session2)]), patch(
            "app.modules.visual.service.project_material_mode", return_value="ai"
        ), patch("app.tasks_autopilot.wait_if_job_paused"), patch("app.tasks_autopilot.autopilot_get_job_status", return_value="done"), patch(
            "app.tasks_autopilot.autopilot_mark_stage"
        ) as mark_stage:
            run_autopilot_media_stage(job_id=5, project_id=1, pid=1, wf="mix", autofill_media_local=None, generate_images_local=self._generate_ok)

        self.assertEqual(self.calls, [(5, 1, False, False)])
        mark_stage.assert_any_call(5, "media", status="done", progress=66, message="生成视频：镜头图片已生成", substage="verify_images")

    def test_ai_media_stage_surfaces_generation_failure_detail(self):
        project = SimpleNamespace(id=1)
        session = _Session(queue=[[project]])

        with patch("app.tasks_autopilot.session_scope", return_value=nullcontext(session)), patch(
            "app.modules.visual.service.project_material_mode", return_value="ai"
        ), patch("app.tasks_autopilot.wait_if_job_paused"), patch(
            "app.tasks_autopilot.autopilot_get_job_status", return_value="failed"
        ), patch("app.tasks_autopilot.autopilot_job_message", return_value="scene 2: request timeout after 50s"):
            with self.assertRaisesRegex(RuntimeError, "服务处理超时，请稍后重试"):
                run_autopilot_media_stage(job_id=5, project_id=1, pid=1, wf="mix", autofill_media_local=None, generate_images_local=self._generate_ok)

        self.assertEqual(self.calls, [(5, 1, False, False)])

    def test_network_media_stage_surfaces_autofill_failure_detail(self):
        project = SimpleNamespace(id=1)
        session = _Session(queue=[[project]])

        with patch("app.tasks_autopilot.session_scope", return_value=nullcontext(session)), patch(
            "app.modules.visual.service.project_material_mode", return_value="network"
        ), patch("app.tasks_autopilot.wait_if_job_paused"), patch("app.tasks_autopilot.autopilot_get_job_status", return_value="failed"), patch(
            "app.tasks_autopilot.autopilot_job_message", return_value="Pexels quota exceeded"
        ):
            with self.assertRaisesRegex(RuntimeError, "Pexels quota exceeded"):
                run_autopilot_media_stage(job_id=5, project_id=1, pid=1, wf="mix", autofill_media_local=self._autofill_fail, generate_images_local=None)

        self.assertEqual(self.autofill_calls, [(5, 1, "video")])

    def setUp(self):
        self.calls = []
        self.autofill_calls = []

    def _generate_ok(self, job_id: int, project_id: int, *, force: bool, manage_job_state: bool = True):
        self.calls.append((job_id, project_id, force, manage_job_state))

    def _autofill_fail(self, job_id: int, project_id: int, *, prefer: str, outer_job_id: int, progress_base: int, progress_span: int, keep_running: bool):
        self.autofill_calls.append((job_id, project_id, prefer))


if __name__ == "__main__":
    unittest.main()
