import json
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from app.api_scenes import bind_scene_asset_api, list_scene_image_assets_api, patch_scene_api, use_scene_image_api
from app.schemas import SceneBindAssetIn, ScenePatchIn


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _Session:
    def __init__(self, queue=None):
        self.queue = list(queue or [])
        self.added = []

    def exec(self, _query):
        rows = self.queue.pop(0) if self.queue else []
        return _Rows(rows)

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        return None

    def refresh(self, _obj):
        return None
class ChannelAndSceneRouterTests(unittest.TestCase):
    def test_patch_scene_updates_project_script(self):
        scene = SimpleNamespace(id=1, project_id=7, idx=1, narration="旧", media_query="", image_prompt="", image_negative="", duration_sec=3.0, meta_json="{}", status="pending", image_asset_id=None)
        scene2 = SimpleNamespace(id=2, project_id=7, idx=2, narration="第二句", media_query="", image_prompt="", image_negative="", duration_sec=3.0, meta_json="{}", status="pending", image_asset_id=None)
        project = SimpleNamespace(id=7, script="", updated_at=None)
        session = _Session(queue=[[scene], [scene, scene2], [project]])
        with patch("app.api_scenes.session_scope", return_value=nullcontext(session)), patch("app.api_scenes.scene_to_out", side_effect=lambda _s, obj: obj):
            out = patch_scene_api(1, ScenePatchIn(narration="第一句"))
        self.assertEqual(out.narration, "第一句")
        self.assertEqual(project.script, "第一句\n第二句")

    def test_bind_scene_asset_rejects_foreign_project_asset(self):
        scene = SimpleNamespace(id=1, project_id=7, status="pending")
        asset = SimpleNamespace(id=9, kind="image", project_id=8)
        session = _Session(queue=[[scene], [asset]])
        with patch("app.api_scenes.session_scope", return_value=nullcontext(session)):
            with self.assertRaisesRegex(Exception, "素材不属于当前项目"):
                bind_scene_asset_api(1, SceneBindAssetIn(asset_id=9))

    def test_list_scene_image_assets_uses_presenter(self):
        assets = [SimpleNamespace(id=1), SimpleNamespace(id=None), SimpleNamespace(id=2)]
        session = _Session(queue=[assets])
        with patch("app.api_scenes.session_scope", return_value=nullcontext(session)), patch("app.api_scenes.asset_to_out", side_effect=lambda a: f"asset-{a.id}"):
            out = list_scene_image_assets_api(1, 10)
        self.assertEqual(out, ["asset-1", "asset-2"])

    def test_use_scene_image_updates_selection(self):
        scene = SimpleNamespace(id=1, project_id=7, image_asset_id=None, updated_at=None)
        asset = SimpleNamespace(id=5, kind="video", scene_id=1, project_id=7)
        session = _Session(queue=[[scene], [asset]])
        with patch("app.api_scenes.session_scope", return_value=nullcontext(session)), patch("app.api_scenes.scene_to_out", side_effect=lambda _s, obj: obj):
            out = use_scene_image_api(1, 5)
        self.assertEqual(out.image_asset_id, 5)


if __name__ == "__main__":
    unittest.main()
