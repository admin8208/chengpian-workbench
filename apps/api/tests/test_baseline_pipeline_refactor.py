import unittest
from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.modules.pipeline.service import continue_pipeline_api, start_pipeline_api
from app.modules.storyboard.service import save_storyboard
from app.modules.baseline.service import prepare_project_script


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _Session:
    def __init__(self, project=None, pack=None, scenes=None):
        self.project = project
        self.pack = pack
        self.scenes = list(scenes or [])
        self.added = []
        self.deleted = []

    def exec(self, query):
        text = str(query)
        if "FROM project" in text:
            return SimpleNamespace(first=lambda: self.project)
        if "FROM channelpack" in text:
            return SimpleNamespace(first=lambda: self.pack)
        if "FROM scene" in text:
            return _Rows(self.scenes)
        if "FROM contentbaselinerevision" in text:
            return _Rows([])
        if "FROM storyboardrevision" in text:
            return _Rows([])
        return SimpleNamespace(first=lambda: None)

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)

    def flush(self):
        return None

    def refresh(self, _obj):
        return None


class BaselinePipelineRefactorTests(unittest.TestCase):
    def test_prepare_project_script_only_updates_script_without_touching_scenes(self):
        project = SimpleNamespace(
            id=8,
            title="测试主题",
            channel_key="history",
            workflow="mix",
            source_text="一些原文",
            character_profile="",
            script="",
            script_source="",
            updated_at=None,
            render_config=lambda: {"input_mode": "text"},
        )
        pack = SimpleNamespace(key="history")
        session1 = _Session(project=project, pack=pack)
        session2 = _Session(project=project, pack=pack, scenes=[SimpleNamespace(id=1), SimpleNamespace(id=2)])
        with patch("app.modules.baseline.service.session_scope", side_effect=[nullcontext(session1), nullcontext(session2)]), patch(
            "app.modules.baseline.service.get_default_provider", return_value=SimpleNamespace(id=3, enabled=True)
        ), patch("app.modules.baseline.service.get_api_key", return_value="k"), patch(
            "app.modules.baseline.service.llm_generate_script_draft", return_value="新文案"
        ):
            out = prepare_project_script(8, project_to_out=lambda _session, p: p)
        self.assertEqual(getattr(out, "script", ""), "新文案")
        self.assertEqual(getattr(out, "script_source", ""), "llm")
        self.assertEqual(session2.deleted, [])

    def test_start_pipeline_requires_confirmed_script(self):
        project = SimpleNamespace(id=9)
        session = _Session(project=project)
        with patch("app.modules.pipeline.service.session_scope", return_value=nullcontext(session)):
            with self.assertRaises(HTTPException) as ctx:
                start_pipeline_api(9)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("请先确认文案", str(ctx.exception.detail))

    def test_continue_pipeline_normalizes_pipeline_run_resume_stage(self):
        project = SimpleNamespace(id=9, confirmed_baseline_revision_id=3, current_pipeline_run_id=8)
        prev = SimpleNamespace(id=12, root_job_id=12, retry_seq=0)
        pipeline_run = SimpleNamespace(id=8, resume_from_stage="audio_subtitle_finalize")
        session = _Session(project=project)
        now = datetime.now(UTC)
        created_job = {"id": 13, "kind": "autopilot", "project_id": 9, "status": "queued", "progress": 0, "message": "", "payload_json": "{}", "created_at": now, "updated_at": now}
        with patch("app.modules.pipeline.service.session_scope", return_value=nullcontext(session)), patch(
            "app.modules.pipeline.service.latest_autopilot_job", side_effect=[None, prev]
        ), patch("app.modules.pipeline.service.get_job_payload", return_value={}), patch(
            "app.modules.pipeline.service.get_pipeline_run", return_value=pipeline_run
        ), patch(
            "app.modules.pipeline.service.autopilot_preflight", return_value=(True, {})
        ), patch("app.modules.pipeline.service.enqueue_project_job", return_value=created_job) as enqueue_job:
            out = continue_pipeline_api(9)
        self.assertTrue(out.ok)
        self.assertEqual(enqueue_job.call_args.kwargs["payload"]["resume_from_stage"], "tts")
        self.assertEqual(enqueue_job.call_args.kwargs["payload"]["current_stage"], "tts")

    def test_save_storyboard_replaces_previous_scenes(self):
        project = SimpleNamespace(id=5, status="draft", script="旧文案", updated_at=None)
        old_scenes = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
        session = _Session(project=project, scenes=old_scenes)
        with patch("app.modules.storyboard.service.session_scope", return_value=nullcontext(session)):
            ok = save_storyboard(5, "新文案", [{"idx": 1, "narration": "镜头一"}, {"idx": 2, "narration": "镜头二"}], update_project_status=True)
        self.assertTrue(ok)
        self.assertEqual(project.script, "新文案")
        self.assertEqual(project.status, "processing")
        self.assertEqual(len(session.deleted), 2)
        self.assertGreaterEqual(len(session.added), 3)

    def test_save_storyboard_keeps_confirmed_script_baseline(self):
        project = SimpleNamespace(id=6, status="draft", script="用户确认文案", confirmed_baseline_revision_id=12, updated_at=None)
        session = _Session(project=project, scenes=[])
        with patch("app.modules.storyboard.service.session_scope", return_value=nullcontext(session)):
            ok = save_storyboard(6, "分镜模型改写文案", [{"idx": 1, "narration": "镜头一"}], update_project_status=True)
        self.assertTrue(ok)
        self.assertEqual(project.script, "用户确认文案")
        self.assertEqual(project.status, "processing")


if __name__ == "__main__":
    unittest.main()
