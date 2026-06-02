import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.api.project_assets import import_project_asset
from app.schemas import LibraryImportIn


def test_import_project_asset_writes_project_scoped_asset():
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_asset = SimpleNamespace(id=99, kind="image", tag="project_source", project_id=7, rel_path="project_7/imported/image/img_hash.jpg", mime="image/jpeg", meta_json="{}", created_at=None)
        project = SimpleNamespace(id=7)

        class _Rows:
            def __init__(self, obj):
                self.obj = obj

            def first(self):
                return self.obj

        class _Session:
            def exec(self, _query):
                return _Rows(project)

        class _Scope:
            def __enter__(self):
                return _Session()

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("app.api.project_assets.session_scope", return_value=_Scope()), patch(
            "app.api.project_assets.import_to_project", return_value=fake_asset
        ) as import_to_project, patch("app.api.project_assets.asset_to_out", side_effect=lambda a: a):
            out = import_project_asset(
                7,
                LibraryImportIn(
                    provider="pixabay",
                    kind="image",
                    title="demo",
                    page_url="https://example.com/page",
                    file_url="https://example.com/img.jpg",
                ),
            )

        assert out.project_id == 7
        assert out.tag == "project_source"
        import_to_project.assert_called_once()
