import json
import unittest

from app.models import Scene
from app.project_summary_metrics import duplicate_scene_asset_ids


def _scene(scene_id: int, asset_id: int, *, asset_kind: str = "video", clip_start=None, clip_end=None) -> Scene:
    render = {"asset_kind": asset_kind}
    if clip_start is not None:
        render["clip_start_sec"] = clip_start
    if clip_end is not None:
        render["clip_end_sec"] = clip_end
    return Scene(
        id=scene_id,
        project_id=1,
        idx=scene_id,
        duration_sec=4.0,
        image_asset_id=asset_id,
        meta_json=json.dumps({"render": render}, ensure_ascii=True),
    )


class ProjectSummaryDuplicateAssetsTests(unittest.TestCase):
    def test_non_overlapping_video_segments_are_not_duplicates(self):
        scenes = [
            _scene(1, 100, clip_start=0, clip_end=4),
            _scene(2, 100, clip_start=4, clip_end=10),
        ]
        self.assertEqual(duplicate_scene_asset_ids(scenes), set())

    def test_overlapping_video_segments_are_duplicates(self):
        scenes = [
            _scene(1, 100, clip_start=0, clip_end=4),
            _scene(2, 100, clip_start=1, clip_end=4.5),
        ]
        self.assertEqual(duplicate_scene_asset_ids(scenes), {1, 2})

    def test_reused_image_asset_remains_duplicate(self):
        scenes = [
            _scene(1, 100, asset_kind="image"),
            _scene(2, 100, asset_kind="image"),
        ]
        self.assertEqual(duplicate_scene_asset_ids(scenes), {1, 2})


if __name__ == "__main__":
    unittest.main()
