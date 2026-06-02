import unittest
from unittest.mock import patch

from app.tasks_storyboard_bridge import llm_rewrite_storyboard_bridge
from app.tasks_storyboard_entry_impl import generate_storyboard_local, rewrite_storyboard_local
from app.tasks_storyboard import llm_generate_storyboard


class TasksStoryboardEntryImplTests(unittest.TestCase):
    def test_generate_storyboard_local_fails_fast_when_cancelled(self):
        with patch("app.tasks_storyboard_entry_impl.abort_if_job_cancelled", return_value=True), patch(
            "app.tasks_storyboard_entry_impl.update_job"
        ) as update_job:
            generate_storyboard_local(
                3,
                9,
                topic=None,
                select_project=lambda *_args, **_kwargs: None,
                get_pack=lambda *_args, **_kwargs: None,
                fail_job=lambda *_args, **_kwargs: None,
                get_default_provider=lambda *_args, **_kwargs: None,
                get_api_key=lambda *_args, **_kwargs: "",
                llm_generate_storyboard=lambda *_args, **_kwargs: ("", []),
            )
        update_job.assert_not_called()

    def test_rewrite_storyboard_local_fails_fast_when_cancelled(self):
        with patch("app.tasks_storyboard_entry_impl.abort_if_job_cancelled", return_value=True), patch(
            "app.tasks_storyboard_entry_impl.update_job"
        ) as update_job:
            rewrite_storyboard_local(
                4,
                10,
                select_project=lambda *_args, **_kwargs: None,
                get_pack=lambda *_args, **_kwargs: None,
                fail_job=lambda *_args, **_kwargs: None,
                get_default_provider=lambda *_args, **_kwargs: None,
                get_api_key=lambda *_args, **_kwargs: "",
                llm_rewrite_storyboard=lambda *_args, **_kwargs: ("", []),
            )
        update_job.assert_not_called()

    def test_llm_generate_storyboard_passes_material_mode_from_render_cfg(self):
        pack = type("Pack", (), {"config": lambda _self: {"hook_style": "sharp"}})()
        with patch("app.tasks_storyboard.generate_storyboard_via_llm", return_value=("脚本", [])) as gen:
            out = llm_generate_storyboard("主题", pack, provider=object(), api_key="", render_cfg={"material_mode": "ai"})
        self.assertEqual(out, ("脚本", []))
        self.assertEqual(gen.call_args.kwargs.get("material_mode"), "ai")

    def test_llm_rewrite_storyboard_bridge_passes_material_mode(self):
        pack = object()
        provider = object()
        with patch("app.tasks_storyboard_bridge.storyboard_llm_rewrite_storyboard", return_value=("脚本", [])) as rewrite:
            out = llm_rewrite_storyboard_bridge(
                "原文",
                pack,
                provider,
                "k",
                render_cfg={"material_mode": "network"},
                material_mode="ai",
            )
        self.assertEqual(out, ("脚本", []))
        self.assertEqual(rewrite.call_args.kwargs.get("material_mode"), "ai")


if __name__ == "__main__":
    unittest.main()
