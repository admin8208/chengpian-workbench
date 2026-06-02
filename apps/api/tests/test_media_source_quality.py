import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.media.web_search import _get_cache_key, provider_aspect_orientation, readable_title_from_url
from app.modules.media.web_search import search_web_media_parallel
from app.tasks_media_search import rank_items


class MediaSourceQualityTests(unittest.TestCase):
    def test_provider_aspect_orientation_handles_numeric_ratios(self):
        self.assertEqual(provider_aspect_orientation("pexels", "0.5625"), "portrait")
        self.assertEqual(provider_aspect_orientation("pexels", "1.7777777777777777"), "landscape")
        self.assertEqual(provider_aspect_orientation("pexels", "1"), "square")
        self.assertEqual(provider_aspect_orientation("pixabay", "0.5625"), "vertical")
        self.assertEqual(provider_aspect_orientation("pixabay", "1.7777777777777777"), "horizontal")

    def test_cache_key_is_stable_and_does_not_use_runtime_hash(self):
        key1 = _get_cache_key("pexels", "video", "office meeting", "1.7777777777777777")
        key2 = _get_cache_key("pexels", "video", "office meeting", "1.7777777777777777")
        key3 = _get_cache_key("pexels", "video", "family dinner", "1.7777777777777777")
        self.assertEqual(key1, key2)
        self.assertNotEqual(key1, key3)
        self.assertNotIn("office", key1)

    def test_readable_title_from_pexels_video_url_removes_numeric_id(self):
        title = readable_title_from_url("https://www.pexels.com/video/exploring-traditional-chinese-architecture-36502493/")
        self.assertEqual(title, "exploring traditional chinese architecture")

    def test_life_tracks_demote_wikimedia_below_pexels_when_other_signals_match(self):
        pexels_item = SimpleNamespace(
            provider="pexels",
            kind="video",
            title="office meeting laptop",
            width=1920,
            height=1080,
            duration_sec=8.0,
        )
        wiki_item = SimpleNamespace(
            provider="wikimedia",
            kind="video",
            title="office meeting laptop",
            width=1920,
            height=1080,
            duration_sec=8.0,
        )
        ranked = rank_items(
            items=[wiki_item, pexels_item],
            expected_dur=4.0,
            query="office meeting laptop",
            scene_meta={},
            prev_scene_meta=None,
            pack_key="career",
            tr=16 / 9,
            prefer="video",
            used_asset_types=[],
            used_providers=[],
            human_shot_bias=lambda *_args: 0.0,
        )
        self.assertIs(ranked[0], pexels_item)

    def test_parallel_search_reports_provider_failures(self):
        failures = []

        def _fail_search(**kwargs):
            if kwargs["provider"] == "pexels":
                raise RuntimeError("pexels quota exceeded")
            return []

        with patch("app.modules.media.web_search.search_web_media", side_effect=_fail_search):
            items = search_web_media_parallel(
                kinds=["image"],
                query="office meeting",
                limit=2,
                provider_keys={"pexels": "key"},
                provider_failure_cb=lambda provider, detail, kind, query: failures.append((provider, detail, kind, query)),
            )

        self.assertEqual(items, [])
        self.assertIn(("pexels", "pexels quota exceeded", "image", "office meeting"), failures)


if __name__ == "__main__":
    unittest.main()
