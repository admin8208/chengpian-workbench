import unittest
from datetime import UTC, datetime
from types import SimpleNamespace

from app.presenters import project_to_out


class _Session:
    def exec(self, _query):
        return SimpleNamespace(first=lambda: None)


class ProjectPresenterRevisionTests(unittest.TestCase):
    def test_project_to_out_includes_revision_and_pipeline_fields(self):
        project = SimpleNamespace(
            id=3,
            title="项目",
            workflow="mix",
            channel_key="history",
            status="draft",
            script="文案",
            script_source="llm",
            source_text="",
            character_profile="",
            publish_title="",
            publish_hashtags="",
            voice_asset_id=None,
            subtitle_asset_id=None,
            role_image_asset_id=None,
            confirmed_baseline_revision_id=12,
            current_pipeline_run_id=34,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            render_config=lambda: {"input_mode": "text"},
        )
        out = project_to_out(_Session(), project)
        self.assertEqual(out.confirmed_baseline_revision_id, 12)
        self.assertEqual(out.current_pipeline_run_id, 34)


if __name__ == "__main__":
    unittest.main()
