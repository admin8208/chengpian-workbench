import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.creator.project_mutation_service import patch_project_api


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _Session:
    def __init__(self, project=None):
        self.project = project
        self.baselines = [SimpleNamespace(id=9, project_id=5, status="confirmed", updated_at=None)]
        self.storyboards = [SimpleNamespace(id=3, project_id=5, status="ready", updated_at=None)]
        self.audio_revs = [SimpleNamespace(id=4, project_id=5, status="ready", updated_at=None)]
        self.pipeline_runs = [SimpleNamespace(id=7, project_id=5, status="running", error_code="", error_detail="", resume_from_stage="", finished_at=None, updated_at=None)]
        self.added = []

    def exec(self, query):
        text = str(query)
        if "FROM project" in text:
            return _Rows([self.project] if self.project else [])
        if "FROM contentbaselinerevision" in text:
            return _Rows(self.baselines)
        if "FROM storyboardrevision" in text:
            return _Rows(self.storyboards)
        if "FROM audiosubtitlerevision" in text:
            return _Rows(self.audio_revs)
        if "FROM pipelinerun" in text:
            return _Rows(self.pipeline_runs)
        return _Rows([])

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        return None

    def refresh(self, _obj):
        return None


class BaselineInvalidationTests(unittest.TestCase):
    def test_patch_project_invalidates_confirmed_chain_on_script_edit(self):
        project = SimpleNamespace(
            id=5,
            title="项目",
            script="旧文案",
            script_source="llm",
            source_text="原文",
            character_profile="",
            publish_title="",
            publish_hashtags="",
            voice_asset_id=None,
            subtitle_asset_id=None,
            confirmed_baseline_revision_id=9,
            current_pipeline_run_id=7,
            updated_at=None,
            render_config=lambda: {"material_mode": "network"},
        )
        body = SimpleNamespace(
            title=None,
            script="新文案",
            source_text=None,
            character_profile=None,
            publish_title=None,
            publish_hashtags=None,
            voice_asset_id=None,
            subtitle_asset_id=None,
            render_config=None,
        )
        session = _Session(project=project)
        with patch("app.modules.creator.project_mutation_service.session_scope", return_value=nullcontext(session)):
            out = patch_project_api(5, body, project_to_out=lambda _session, p: p, normalize_subtitle_settings=lambda style, cfg: (style, cfg))
        self.assertEqual(out.script_source, "manual")
        self.assertIsNone(out.confirmed_baseline_revision_id)
        self.assertIsNone(out.current_pipeline_run_id)
        self.assertEqual(session.baselines[0].status, "superseded")
        self.assertEqual(session.storyboards[0].status, "stale")
        self.assertEqual(session.audio_revs[0].status, "stale")
        self.assertEqual(session.pipeline_runs[0].status, "failed")


if __name__ == "__main__":
    unittest.main()
