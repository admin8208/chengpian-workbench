import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from app.application.feed import get_project_center_feed_from_projection


class FeedProjectionCleanupTests(unittest.TestCase):
    def test_project_center_feed_filters_missing_project_projections(self):
        rows = [
            SimpleNamespace(
                project_id=1,
                payload_json=(
                    '{'
                    '"project_id":1,'
                    '"title":"已删除项目",'
                    '"workflow":"mix",'
                    '"channel_key":"emotion",'
                    '"material_mode":"ai",'
                    '"material_mode_label":"AI 镜头图",'
                    '"open_path":"/p/ai/1",'
                    '"tone":"",'
                    '"status":"draft",'
                    '"status_label":"未开始",'
                    '"stage_text":"未开始",'
                    '"notice":"项目状态正常，可打开项目查看并处理。",'
                    '"action_key":"open_project",'
                    '"action_label":"打开项目",'
                    '"tags":[],'
                    '"final_exists":false,'
                    '"emphasize_asset_issues":false,'
                    '"missing_asset_label":"缺镜头图",'
                    '"missing_asset_count":0,'
                    '"duplicate_asset_count":0,'
                    '"continue_stage_label":"",'
                    '"needs_llm_settings":false,'
                    '"needs_media_settings":false,'
                    '"needs_tts_settings":false,'
                    '"can_delete":true,'
                    '"updated_at":"2026-05-17T00:00:00Z",'
                    '"updated_at_text":"2026-05-17 08:00",'
                    '"current_job":null,'
                    '"current_job_is_active":false'
                    '}'
                ),
            ),
            SimpleNamespace(
                project_id=2,
                payload_json=(
                    '{'
                    '"project_id":2,'
                    '"title":"有效项目",'
                    '"workflow":"mix",'
                    '"channel_key":"history",'
                    '"material_mode":"network",'
                    '"material_mode_label":"联网素材",'
                    '"open_path":"/p/network/2",'
                    '"tone":"",'
                    '"status":"draft",'
                    '"status_label":"未开始",'
                    '"stage_text":"未开始",'
                    '"notice":"项目状态正常，可打开项目查看并处理。",'
                    '"action_key":"open_project",'
                    '"action_label":"打开项目",'
                    '"tags":[],'
                    '"final_exists":false,'
                    '"emphasize_asset_issues":false,'
                    '"missing_asset_label":"缺素材",'
                    '"missing_asset_count":0,'
                    '"duplicate_asset_count":0,'
                    '"continue_stage_label":"",'
                    '"needs_llm_settings":false,'
                    '"needs_media_settings":false,'
                    '"needs_tts_settings":false,'
                    '"can_delete":true,'
                    '"updated_at":"2026-05-17T00:01:00Z",'
                    '"updated_at_text":"2026-05-17 08:01",'
                    '"current_job":null,'
                    '"current_job_is_active":false'
                    '}'
                ),
            ),
        ]

        fake_session = SimpleNamespace(
            exec=lambda _query: SimpleNamespace(all=lambda: [2])
        )

        with patch('app.application.feed.load_project_projection_rows', return_value=rows), patch(
            'app.application.feed.session_scope', return_value=nullcontext(fake_session)
        ), patch('app.application.feed.delete_project_projection') as delete_project_projection, patch(
            'app.application.feed.delete_job_projections'
        ) as delete_job_projections:
            feed = get_project_center_feed_from_projection(limit=200)

        self.assertEqual(feed.stats.all, 1)
        self.assertEqual(len(feed.items), 1)
        self.assertEqual(feed.items[0].project_id, 2)
        delete_project_projection.assert_called_once_with(1)
        delete_job_projections.assert_called_once_with(1)


if __name__ == '__main__':
    unittest.main()
