import unittest
from datetime import UTC, datetime
from types import SimpleNamespace

from app.presenters import project_to_out


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None


class _Session:
    def exec(self, _query):
        return _Rows([])


class PresenterProjectOutputTests(unittest.TestCase):
    def test_project_output_no_longer_contains_runtime_fields(self):
        project = SimpleNamespace(
            id=9,
            title="测试项目",
            workflow="mix",
            channel_key="career",
            status="draft",
            script="脚本",
            source_text="原文",
            character_profile="",
            publish_title="",
            publish_hashtags="",
            role_image_asset_id=None,
            voice_asset_id=None,
            subtitle_asset_id=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            render_config=lambda: {"aspect": "landscape"},
        )

        out = project_to_out(_Session(), project)
        dumped = out.model_dump()

        self.assertNotIn("workflow_stage", dumped)
        self.assertNotIn("continue_stage", dumped)
        self.assertNotIn("active_job_status", dumped)
        self.assertNotIn("next_action", dumped)
        self.assertEqual(dumped["title"], "测试项目")


if __name__ == "__main__":
    unittest.main()
