import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.llm_client import LlmError
from app.tasks_autopilot import build_confirmed_script_storyboard, run_autopilot_storyboard_stage


class TasksAutopilotStoryboardStrictTests(unittest.TestCase):
    def test_confirmed_script_storyboard_ai_prompt_is_visual_and_concrete(self):
        pack = SimpleNamespace(key="career", config=lambda: {"scene_count": 3, "scene_duration_sec": 4, "style": "cinematic realism"})
        script, scenes = build_confirmed_script_storyboard(
            "她进会议室时先停了一下。然后把准备好的话又咽了回去。",
            pack=pack,
            render_cfg={"material_mode": "ai"},
            material_mode="ai",
        )
        self.assertTrue(script)
        self.assertGreaterEqual(len(scenes), 1)
        prompt = scenes[0]["image_prompt"]
        self.assertIn("Chinese cinematic realism", prompt)
        self.assertIn("wide cinematic framing with safe side margins", prompt)
        self.assertIn("horizontal 16:9", prompt)

    def test_confirmed_script_storyboard_supports_portrait_prompt_direction(self):
        pack = SimpleNamespace(key="career", config=lambda: {"scene_count": 3, "scene_duration_sec": 4, "style": "cinematic realism"})
        script, scenes = build_confirmed_script_storyboard(
            "她进会议室时先停了一下。然后把准备好的话又咽了回去。",
            pack=pack,
            render_cfg={"material_mode": "ai", "aspect": "portrait"},
            material_mode="ai",
        )
        self.assertTrue(script)
        self.assertGreaterEqual(len(scenes), 1)
        prompt = scenes[0]["image_prompt"]
        self.assertIn("vertical 9:16", prompt)

    def test_confirmed_script_storyboard_does_not_call_rewrite(self):
        project = SimpleNamespace(voice_asset_id=None, script="第一句确认文案。第二句确认文案。", confirmed_baseline_revision_id=3)
        pack = SimpleNamespace(key="history", config=lambda: {"scene_count": 8, "scene_duration_sec": 4})

        calls = {"rewrite": 0, "save": None}

        def _rewrite(*_args, **_kwargs):
            calls["rewrite"] += 1
            return "被改写", [{"idx": 1, "narration": "被改写", "duration_sec": 4}]

        def _save(pid, script, scenes, *, update_project_status):
            calls["save"] = (pid, script, scenes, update_project_status)
            return True

        with patch("app.tasks_autopilot.project_input_mode", return_value="text"), patch(
            "app.tasks_autopilot.project_has_confirmed_baseline", return_value=True
        ), patch("app.tasks_autopilot.wait_if_job_paused"), patch("app.tasks_autopilot.autopilot_mark_stage"), patch(
            "app.tasks_autopilot.patch_job_payload"
        ), patch("app.tasks_autopilot.update_job"), patch("app.tasks_autopilot.save_autopilot_storyboard", side_effect=_save), patch(
            "app.tasks_autopilot.check_text", return_value=[]
        ):
            run_autopilot_storyboard_stage(
                job_id=7,
                pid=3,
                title="测试主题",
                src="",
                project=project,
                channel_key="history",
                character_profile="",
                wf="mix",
                pack=pack,
                provider=SimpleNamespace(enabled=True),
                api_key="k",
                render_cfg={"material_mode": "network"},
                llm_rewrite_storyboard=_rewrite,
                llm_generate_storyboard=lambda *_args, **_kwargs: ("", []),
            )

        self.assertEqual(calls["rewrite"], 0)
        self.assertIsNotNone(calls["save"])
        _pid, script, scenes, _status = calls["save"]
        self.assertEqual(script, "第一句确认文案。第二句确认文案。")
        self.assertEqual("".join(s["narration"] for s in scenes), script)

    def test_storyboard_stage_timeout_no_longer_falls_back(self):
        project = SimpleNamespace(voice_asset_id=None)
        pack = SimpleNamespace(key="history")
        def _raise_timeout(*_args, **_kwargs):
            raise LlmError("request timeout after 20s")

        with patch("app.tasks_autopilot.project_input_mode", return_value="text"), patch(
            "app.tasks_autopilot.wait_if_job_paused"
        ), patch("app.tasks_autopilot.autopilot_mark_stage"), patch("app.tasks_autopilot.patch_job_payload"), patch(
            "app.tasks_autopilot.update_job"
        ), patch("app.tasks_autopilot.classify_llm_failure", return_value=("llm_timeout", "大模型请求超时")):
            with self.assertRaises(RuntimeError) as ctx:
                run_autopilot_storyboard_stage(
                    job_id=7,
                    pid=3,
                    title="测试主题",
                    src="",
                    project=project,
                    channel_key="history",
                    character_profile="",
                    wf="mix",
                    pack=pack,
                    provider=SimpleNamespace(enabled=True),
                    api_key="k",
                    render_cfg={},
                    llm_rewrite_storyboard=lambda *_args, **_kwargs: ("", []),
                    llm_generate_storyboard=_raise_timeout,
                )
        self.assertIn("分镜大模型生成失败：大模型请求超时", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
