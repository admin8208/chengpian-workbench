import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.pipeline.orchestrator import run_pipeline_job


class _Session:
    def __init__(self, project=None, pack=None):
        self.project = project
        self.pack = pack
        self.added = []

    def exec(self, query):
        text = str(query)
        if "FROM project" in text:
            return SimpleNamespace(first=lambda: self.project)
        if "FROM channelpack" in text:
            return SimpleNamespace(first=lambda: self.pack)
        return SimpleNamespace(first=lambda: None)

    def add(self, obj):
        self.added.append(obj)


class PipelineOrchestratorTests(unittest.TestCase):
    def test_orchestrator_reuses_done_storyboard_and_runs_tts_before_visual_and_render(self):
        calls: list[str] = []
        project = SimpleNamespace(id=11, title="t", channel_key="history", source_text="", character_profile="", render_config=lambda: {}, status="draft")
        pack = SimpleNamespace(key="history")
        with patch("app.modules.pipeline.orchestrator.session_scope", return_value=nullcontext(_Session(project=project, pack=pack))), patch(
            "app.modules.pipeline.orchestrator.patch_job_payload"
        ), patch("app.modules.pipeline.orchestrator.update_job") as update_job, patch(
            "app.tasks_autopilot.autopilot_payload", return_value={"storyboard_done": True}
        ), patch("app.tasks_autopilot.autopilot_resume_stage", return_value=None), patch(
            "app.tasks_autopilot.autopilot_preflight", return_value=(True, {"provider": None, "api_key": ""})
        ), patch("app.tasks_autopilot.autopilot_stage_done", side_effect=lambda _job_id, stage: stage == "storyboard"), patch(
            "app.tasks_autopilot.run_autopilot_storyboard_stage"
        ) as storyboard_stage, patch("app.modules.pipeline.orchestrator.run_visual_stage", side_effect=lambda **_kwargs: calls.append("visual")), patch(
            "app.tasks_autopilot.run_autopilot_tts_stage", side_effect=lambda **_kwargs: calls.append("tts")
        ), patch(
            "app.tasks_autopilot.run_autopilot_render_stage", side_effect=lambda **_kwargs: calls.append("render")
        ):
            run_pipeline_job(
                3,
                11,
                fail_job=lambda *_args, **_kwargs: None,
                llm_generate_storyboard=lambda *_args, **_kwargs: None,
                llm_rewrite_storyboard=lambda *_args, **_kwargs: None,
                render_video_impl=lambda *_args, **_kwargs: None,
                autofill_media_local=lambda *_args, **_kwargs: None,
                generate_images_local=lambda *_args, **_kwargs: None,
                get_default_provider=lambda _session: None,
                get_api_key=lambda _session, _provider_id: "",
            )
        storyboard_stage.assert_not_called()
        self.assertEqual(calls, ["tts", "visual", "render"])
        self.assertTrue(any("复用已生成分镜" in str(call.kwargs.get("message") or "") for call in update_job.call_args_list))


if __name__ == "__main__":
    unittest.main()
