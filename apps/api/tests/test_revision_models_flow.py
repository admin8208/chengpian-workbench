import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.baseline.service import confirm_project_script, prepare_project_script


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _Session:
    def __init__(self, project=None, pack=None):
        self.project = project
        self.pack = pack
        self.added = []
        self._baseline_rows = []

    def exec(self, query):
        text = str(query)
        if "FROM project" in text:
            return _Rows([self.project] if self.project else [])
        if "FROM channelpack" in text:
            return _Rows([self.pack] if self.pack else [])
        if "FROM contentbaselinerevision" in text:
            return _Rows(self._baseline_rows)
        return _Rows([])

    def add(self, obj):
        self.added.append(obj)
        name = obj.__class__.__name__
        if name == "ContentBaselineRevision":
            if getattr(obj, "id", None) is None:
                obj.id = len(self._baseline_rows) + 1
            self._baseline_rows.append(obj)

    def flush(self):
        return None

    def refresh(self, _obj):
        return None


class RevisionModelsFlowTests(unittest.TestCase):
    def test_prepare_and_confirm_create_baseline_revisions(self):
        project = SimpleNamespace(
            id=12,
            title="测试主题",
            channel_key="history",
            workflow="mix",
            source_text="原文",
            character_profile="",
            script="",
            script_source="",
            confirmed_baseline_revision_id=None,
            voice_asset_id=None,
            updated_at=None,
            render_config=lambda: {"input_mode": "text"},
        )
        pack = SimpleNamespace(key="history")
        session1 = _Session(project=project, pack=pack)
        session2 = _Session(project=project, pack=pack)
        session2._baseline_rows = []
        with patch("app.modules.baseline.service.session_scope", side_effect=[nullcontext(session1), nullcontext(session2)]), patch(
            "app.modules.baseline.service.get_default_provider", return_value=SimpleNamespace(id=2, enabled=True)
        ), patch("app.modules.baseline.service.get_api_key", return_value="k"), patch(
            "app.modules.baseline.service.llm_generate_script_draft", return_value="草稿文案"
        ):
            out = prepare_project_script(12, project_to_out=lambda _session, p: p)
        self.assertEqual(getattr(out, "script", ""), "草稿文案")
        self.assertTrue(any(obj.__class__.__name__ == "ContentBaselineRevision" and obj.status == "draft" for obj in session2.added))

        session3 = _Session(project=project, pack=pack)
        with patch("app.modules.baseline.service.session_scope", return_value=nullcontext(session3)):
            out2 = confirm_project_script(12, script="确认文案", project_to_out=lambda _session, p: p)
        self.assertEqual(getattr(out2, "confirmed_baseline_revision_id", None), 1)
        self.assertTrue(any(obj.__class__.__name__ == "ContentBaselineRevision" and obj.status == "confirmed" for obj in session3.added))


if __name__ == "__main__":
    unittest.main()
