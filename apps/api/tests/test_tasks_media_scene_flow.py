import unittest

from app.tasks_media_scene_flow import retry_scene_candidates, search_scene_candidates


class TasksMediaSceneFlowTests(unittest.TestCase):
    def test_search_scene_candidates_does_not_fallback_to_images_before_library(self):
        image_calls = []

        result = search_scene_candidates(
            candidates=["office team"],
            prefer="video",
            want_new_main_clip=False,
            remaining_expected_dur=12.0,
            expected_dur=4.0,
            scene_meta={},
            scene_deadline=999999.0,
            media_total_deadline=999999.0,
            now_time=lambda: 0.0,
            search_all=lambda _q: [],
            search_images_only=lambda q: image_calls.append(q) or ["image"],
            rank_items=lambda **kwargs: kwargs["items"],
            pick_main_web_item=lambda *_args, **_kwargs: None,
            search_library_assets=lambda _q: [],
            pick_main_library_hit=lambda *_args, **_kwargs: None,
        )

        self.assertEqual(result.web_items, [])
        self.assertEqual(image_calls, [])

    def test_retry_scene_candidates_prefers_video_queries_over_image_only_fallback(self):
        image_calls = []
        searched = []

        def _search_all(query):
            searched.append(query)
            return [query] if query == "office" else []

        result = retry_scene_candidates(
            candidates=["office team"],
            query="office team",
            prefer="video",
            expected_dur=4.0,
            scene_meta={},
            narration="团队开会",
            project_title="职场沟通",
            pack_key="career",
            llm_cfg=None,
            llm_cache={},
            scene_deadline=999999.0,
            media_total_deadline=999999.0,
            now_time=lambda: 0.0,
            clean_query=lambda q: q,
            search_images_only=lambda q: image_calls.append(q) or [],
            search_all=_search_all,
            rank_items=lambda **kwargs: kwargs["items"],
            rewrite_to_en_keywords=lambda _q: "",
            llm_extra_queries=lambda **_kwargs: [],
        )

        self.assertEqual(result.web_items, ["office"])
        self.assertEqual(result.query_used, "office")
        self.assertIn("office", searched)
        self.assertEqual(image_calls, [])


if __name__ == "__main__":
    unittest.main()
