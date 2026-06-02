import tempfile
import unittest
from contextlib import nullcontext
from datetime import datetime, UTC
from types import SimpleNamespace
from unittest.mock import ANY, patch

from app.application.project_ops.service import get_final_export_api, start_render_api, start_render_batch_api
from app.modules.ai_project.project_ops import start_ai_images_api, start_ai_scene_image_api
from app.modules.network_project.project_ops import start_network_autofill_media_api
from app.schemas import JobOut, RenderBatchIn


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
        self.deleted = []
        self.added = []

    def exec(self, _query):
        rows = self.queue.pop(0) if self.queue else []
        return _Rows(rows)

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)

    def flush(self):
        return None

    def refresh(self, _obj):
        return None


class ProjectOpsRouterTests(unittest.TestCase):
    def _job_out_stub(self, job_id: int):
        return JobOut(
            id=job_id,
            kind="render",
            project_id=7,
            status="queued",
            progress=0,
            message="排队中",
            payload_json="{}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    def test_start_render_uses_job_out(self):
        job = self._job_out_stub(5)
        with patch("app.application.project_ops.service.check_render_quality", return_value={"ready": True}), patch(
            "app.application.project_ops.service.enqueue_project_job", return_value=job
        ) as dispatch:
            out = start_render_api(7)
        dispatch.assert_called_once_with(
            kind="render",
            project_id=7,
            message="排队中",
            payload={"project_id": 7, "render_substage": "tts_prepare"},
            enqueue=ANY,
            enqueue_error_message="渲染任务入队失败，请检查后台任务服务",
        )
        self.assertEqual(out.job.id, 5)

    def test_start_render_batch_uses_single_output_payload(self):
        job = self._job_out_stub(8)
        with patch("app.application.project_ops.service.check_render_quality", return_value={"ready": True}), patch(
            "app.application.project_ops.service.enqueue_project_job", return_value=job
        ) as dispatch:
            out = start_render_batch_api(9, RenderBatchIn())
        dispatch.assert_called_once_with(
            kind="render",
            project_id=9,
            message="排队中",
            payload={"project_id": 9, "single_output": True, "render_substage": "tts_prepare"},
            enqueue=ANY,
            enqueue_error_message="批量渲染任务入队失败，请检查后台任务服务",
        )
        self.assertEqual(out.jobs[0].id, 8)

    def test_get_final_export_reports_missing(self):
        with patch("app.application.project_ops.service.stable_final_export_status", return_value={"exists": False}) as stable_status:
            out = get_final_export_api(7)
        stable_status.assert_called_once_with(7)
        self.assertFalse(out["exists"])

    def test_start_images_creates_job_and_dispatches_worker(self):
        job = self._job_out_stub(12)
        with patch("app.modules.ai_project.project_ops._require_project_material_mode", return_value=SimpleNamespace(id=1)), patch(
            "app.modules.ai_project.project_ops.enqueue_project_job", return_value=job
        ) as dispatch:
            out = start_ai_images_api(1)
        dispatch.assert_called_once_with(
            kind="images",
            project_id=1,
            message="排队中",
            payload={"project_id": 1, "force": True},
            enqueue=ANY,
            enqueue_error_message="智能生图任务入队失败，请检查后台任务服务",
        )
        self.assertEqual(out.job.id, 12)

    def test_start_scene_image_creates_job_and_dispatches_worker(self):
        scene = SimpleNamespace(id=2, project_id=9)
        session = _Session(queue=[[scene]])
        job = self._job_out_stub(13)
        with patch("app.modules.ai_project.project_ops.session_scope", return_value=nullcontext(session)), patch(
            "app.modules.ai_project.project_ops._require_project_material_mode", return_value=SimpleNamespace(id=9)
        ), patch(
            "app.modules.ai_project.project_ops.enqueue_project_job", return_value=job
        ) as dispatch:
            out = start_ai_scene_image_api(2)
        dispatch.assert_called_once_with(
            kind="scene_image",
            project_id=9,
            message="排队中",
            payload={"project_id": 9, "scene_id": 2, "force": True},
            enqueue=ANY,
            enqueue_error_message="单镜头生图任务入队失败，请检查后台任务服务",
        )
        self.assertEqual(out.job.id, 13)

    def test_start_autofill_media_normalizes_prefer(self):
        job = self._job_out_stub(6)
        with patch("app.modules.network_project.project_ops._require_project_material_mode", return_value=SimpleNamespace(id=4)), patch(
            "app.modules.network_project.project_ops.enqueue_project_job", return_value=job
        ) as dispatch:
            out = start_network_autofill_media_api(4, "weird")
        dispatch.assert_called_once_with(
            kind="autofill_media",
            project_id=4,
            message="排队中",
            payload={"project_id": 4, "prefer": "video"},
            enqueue=ANY,
            enqueue_error_message="自动补素材任务入队失败，请检查后台任务服务",
        )
        self.assertEqual(out.job.id, 6)

if __name__ == "__main__":
    unittest.main()
