import unittest
from unittest.mock import patch

from app.modules.visual.resolver import resolve_visual_pipeline
from app.tasks_autopilot import humanize_autopilot_detail


def _kwargs():
    return {
        "job_id": 1,
        "project_id": 2,
        "pid": 2,
        "wf": "mix",
        "project": object(),
        "autofill_media_local": object(),
        "generate_images_local": object(),
        "autopilot_mark_stage": object(),
        "autopilot_get_job_status": object(),
        "autopilot_job_message": object(),
        "autopilot_payload": object(),
        "autopilot_scene_stats": object(),
        "humanize_autopilot_detail": object(),
        "update_job": object(),
        "wait_if_job_paused": object(),
    }


class VisualResolverTests(unittest.TestCase):
    def test_network_pipeline_filters_visual_kwargs(self):
        with patch("app.modules.visual.resolver.run_network_visual_stage") as run_network:
            resolve_visual_pipeline("network").run_media_stage(**_kwargs())

        run_network.assert_called_once()
        called = run_network.call_args.kwargs
        self.assertIn("autofill_media_local", called)
        self.assertIn("autopilot_scene_stats", called)
        self.assertNotIn("project", called)
        self.assertNotIn("generate_images_local", called)

    def test_ai_pipeline_filters_visual_kwargs(self):
        with patch("app.modules.visual.resolver.run_ai_visual_stage") as run_ai:
            resolve_visual_pipeline("ai").run_media_stage(**_kwargs())

        run_ai.assert_called_once()
        called = run_ai.call_args.kwargs
        self.assertIn("generate_images_local", called)
        self.assertNotIn("project", called)
        self.assertNotIn("autofill_media_local", called)
        self.assertNotIn("autopilot_scene_stats", called)

    def test_internal_type_error_is_not_reported_as_network_failure(self):
        message = humanize_autopilot_detail("run_network_visual_stage() got an unexpected keyword argument 'project'")

        self.assertEqual(message, "内部流程参数错误，请更新后重试。")


if __name__ == "__main__":
    unittest.main()
