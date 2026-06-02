import unittest

from types import SimpleNamespace

from app.modules.pipeline.state import normalize_autopilot_stage, pipeline_continue_stage


class PipelineStageStateTests(unittest.TestCase):
    def test_normalize_autopilot_stage_maps_pipeline_aliases(self):
        self.assertEqual(normalize_autopilot_stage("storyboard_plan"), "storyboard")
        self.assertEqual(normalize_autopilot_stage("visual_resolve"), "media")
        self.assertEqual(normalize_autopilot_stage("audio_subtitle_finalize"), "tts")
        self.assertEqual(normalize_autopilot_stage("render_finalize"), "render")

    def test_pipeline_continue_stage_prefers_run_and_returns_canonical_stage(self):
        run = SimpleNamespace(resume_from_stage="visual_resolve")
        payload = {"resume_from_stage": "render_finalize"}
        self.assertEqual(pipeline_continue_stage(run, payload), "media")

    def test_pipeline_continue_stage_accepts_legacy_payload_stage(self):
        payload = {"last_failed_stage": "audio_subtitle_finalize"}
        self.assertEqual(pipeline_continue_stage(None, payload), "tts")


if __name__ == "__main__":
    unittest.main()
