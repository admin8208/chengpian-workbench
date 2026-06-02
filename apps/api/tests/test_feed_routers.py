import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas import JobCenterFeedOut, ProjectCenterFeedOut


class FeedRouterTests(unittest.TestCase):
    def test_project_center_feed_prefers_projection(self):
        client = TestClient(app)
        projection_feed = ProjectCenterFeedOut.model_validate({
            "stats": {"all": 1, "running": 0, "failed": 0, "final_ready": 0},
            "items": [
                {
                    "project_id": 1,
                    "title": "项目A",
                    "workflow": "mix",
                    "channel_key": "emotion",
                    "material_mode": "ai",
                    "material_mode_label": "AI 镜头图",
                    "open_path": "/p/ai/1",
                    "tone": "",
                    "status": "draft",
                    "status_label": "未开始",
                    "stage_text": "未开始",
                    "notice": "项目状态正常，可打开项目查看并处理。",
                    "action_key": "open_project",
                    "action_label": "打开项目",
                    "tags": [],
                    "final_exists": False,
                    "emphasize_asset_issues": False,
                    "missing_asset_label": "缺镜头图",
                    "missing_asset_count": 0,
                    "duplicate_asset_count": 0,
                    "continue_stage_label": "",
                    "needs_llm_settings": False,
                    "needs_media_settings": False,
                    "needs_tts_settings": False,
                    "can_delete": True,
                    "updated_at": "2026-05-17T00:00:00Z",
                    "updated_at_text": "2026-05-17 08:00",
                    "current_job": None,
                    "current_job_is_active": False,
                }
            ],
            "server_time": "2026-05-17T00:00:00Z",
        })
        with patch("app.api.auth_web.auth_is_configured", return_value=True), patch(
            "app.api.auth_web.get_authenticated_principal", return_value={"username": "admin", "is_admin": True}
        ), patch("app.api.feed.get_project_center_feed_from_projection", return_value=projection_feed) as projection_api, patch("app.api.feed.schedule_rebuild_all_projections_once") as rebuild_api:
            res = client.get("/api/project-center/feed")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["stats"]["all"], 1)
        projection_api.assert_called_once()
        rebuild_api.assert_not_called()

    def test_project_center_feed_empty_projection_rebuilds_without_realtime_fallback(self):
        client = TestClient(app)
        empty_feed = ProjectCenterFeedOut.model_validate({"stats": {"all": 0, "running": 0, "failed": 0, "final_ready": 0}, "items": [], "server_time": "2026-05-17T00:00:00Z"})
        with patch("app.api.auth_web.auth_is_configured", return_value=True), patch(
            "app.api.auth_web.get_authenticated_principal", return_value={"username": "admin", "is_admin": True}
        ), patch("app.api.feed.get_project_center_feed_from_projection", return_value=empty_feed), patch("app.api.feed.schedule_rebuild_all_projections_once") as rebuild_api:
            res = client.get("/api/project-center/feed")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["stats"]["all"], 0)
        self.assertEqual(res.json()["items"], [])
        self.assertEqual(res.json()["rebuilding"], True)
        rebuild_api.assert_called_once()

    def test_job_center_feed_prefers_projection(self):
        client = TestClient(app)
        projection_feed = JobCenterFeedOut.model_validate({
            "stats": {"all": 1, "active": 1, "failed": 0, "done": 0, "cancelled": 0},
            "items": [
                {
                    "entry_key": "job-1",
                    "entry_type": "job",
                    "project_id": 1,
                    "project_title": "项目A",
                    "project_material_mode": "network",
                    "project_open_path": "/p/network/1",
                    "project_final_exists": False,
                    "status": "running",
                    "status_label": "运行中",
                    "status_tone": "info",
                    "job_id": 1,
                    "root_job_id": 1,
                    "attempt_count": 1,
                    "chain_attempts_label": "",
                    "job_kind": "render",
                    "job_kind_label": "最终成片",
                    "stage_label": "最终成片",
                    "substage_label": "混音与烧录字幕",
                    "message_label": "正在执行最终成片。",
                    "human_hint": "",
                    "progress": 50,
                    "updated_at": "2026-05-17T00:00:00Z",
                    "updated_at_text": "2026-05-17 08:00",
                    "error_code": None,
                    "error_code_label": "",
                    "blocking_component": None,
                    "blocking_component_label": "",
                    "recommended_action": None,
                    "recommended_action_label": "",
                    "is_active": True,
                    "is_deletable": False,
                    "history": [],
                }
            ],
            "server_time": "2026-05-17T00:00:00Z",
        })
        with patch("app.api.auth_web.auth_is_configured", return_value=True), patch(
            "app.api.auth_web.get_authenticated_principal", return_value={"username": "admin", "is_admin": True}
        ), patch("app.api.feed.get_job_center_feed_from_projection", return_value=projection_feed) as projection_api, patch("app.api.feed.schedule_rebuild_all_projections_once") as rebuild_api:
            res = client.get("/api/job-center/feed")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["stats"]["all"], 1)
        projection_api.assert_called_once()
        rebuild_api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
