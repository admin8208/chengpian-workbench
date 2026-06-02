import unittest

from types import SimpleNamespace
from unittest.mock import patch

from app.application.projects.service import project_summary_and_quality


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _Session:
    def __init__(self, summary_job):
        self.summary_job = summary_job

    def exec(self, query):
        text = str(query)
        if "FROM scene" in text:
            return _Rows([])
        if "FROM asset" in text:
            return _Rows([])
        if "FROM job" in text:
            return _Rows([self.summary_job])
        return _Rows([])


class ProjectSummaryStagesTests(unittest.TestCase):
    def test_summary_normalizes_continue_stage_from_pipeline_run(self):
        project = SimpleNamespace(
            id=9,
            title="项目",
            workflow="mix",
            status="failed",
            confirmed_baseline_revision_id=2,
            current_pipeline_run_id=7,
            subtitle_asset_id=None,
            channel_key="history",
            publish_title="",
            publish_hashtags="",
            render_config=lambda: {"input_mode": "text", "subtitle_style": "boxed"},
        )
        summary_job = SimpleNamespace(id=15, kind="autopilot", status="failed", message="失败", created_at=None)
        pipeline_run = SimpleNamespace(status="failed", current_stage="audio_subtitle_finalize", resume_from_stage="audio_subtitle_finalize")
        session = _Session(summary_job)
        with patch("app.application.projects.service.get_pipeline_run", return_value=pipeline_run), patch(
            "app.application.projects.service.get_job_payload", return_value={}
        ), patch("app.application.projects.service.resolve_final_export_status", return_value={"exists": False, "size": 0}), patch(
            "app.application.projects.service.tts_status_dict", return_value={"backend": "edge"}
        ), patch("app.application.projects.service.project_material_mode", return_value="network"), patch(
            "app.application.projects.service.summary_continuity_metrics", return_value={"anchor_coverage": 1.0, "adjacent_jump_rate": 0.0}
        ), patch("app.application.projects.service.summary_main_clip_metrics", return_value={"main_clip_count": 0, "main_clip_coverage": 0}), patch(
            "app.application.projects.service.content_reasonability_metrics", return_value={"score": 100, "items": [], "metrics": {}}
        ):
            summary, _quality = project_summary_and_quality(
                session,
                project,
                latest_autopilot_job=lambda _session, _pid, active_only=False: None,
                autopilot_continue_stage=lambda payload: None,
            )
        self.assertEqual(summary.last_job_stage, "audio_subtitle_finalize")
        self.assertEqual(summary.continue_stage, "tts")


if __name__ == "__main__":
    unittest.main()
