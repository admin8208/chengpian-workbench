import unittest
from types import SimpleNamespace

from app.tasks_image_provider import generate_scene_image_via_provider, image_size_candidates, normalize_image_size


class ImageSizeStrategyTests(unittest.TestCase):
    def test_landscape_project_prefers_horizontal_generation_size(self):
        project = SimpleNamespace(render_config=lambda: {"aspect": "landscape", "width": 1920, "height": 1080})
        self.assertEqual(normalize_image_size(project), "1664x944")
        self.assertEqual(image_size_candidates(project), ["1664x944", "1024x1024"])

    def test_portrait_project_prefers_vertical_generation_size(self):
        project = SimpleNamespace(render_config=lambda: {"aspect": "portrait", "width": 1080, "height": 1920})
        self.assertEqual(normalize_image_size(project), "944x1664")
        self.assertEqual(image_size_candidates(project), ["944x1664", "1024x1024"])

    def test_generate_scene_image_falls_back_when_primary_size_not_supported(self):
        project = SimpleNamespace(render_config=lambda: {"aspect": "landscape", "width": 1920, "height": 1080})
        pack = SimpleNamespace(key="career", config=lambda: {"style": "cinematic realism", "negative": "text"})
        scene = SimpleNamespace(image_prompt="办公室里的人物正在沟通", image_negative="", meta_json="{}")
        provider = SimpleNamespace(id=1, base_url="https://img", default_model="flux", type="openai_compat", name="img")
        calls: list[str] = []

        def _gen(**kwargs):
            calls.append(str(kwargs.get("size")))
            if kwargs.get("size") == "1664x944":
                raise RuntimeError("unsupported size")
            return {"b64_json": "ZmFrZQ=="}

        image_bytes, mime, meta = generate_scene_image_via_provider(
            session=object(),
            provider=provider,
            providers=[provider],
            get_image_api_key=lambda _session, _pid: "key",
            api_key="key",
            project=project,
            pack=pack,
            scene=scene,
            openai_compat_generate_image=_gen,
        )

        self.assertEqual(calls[:3], ["1664x944", "1664x944", "1024x1024"])
        self.assertEqual(meta["size"], "1024x1024")
        self.assertEqual(mime, "image/png")
        self.assertTrue(image_bytes)

    def test_generate_scene_image_falls_back_to_simpler_prompt_after_timeout(self):
        project = SimpleNamespace(render_config=lambda: {"aspect": "landscape", "width": 1920, "height": 1080})
        pack = SimpleNamespace(key="history", config=lambda: {"style": "historical cinematic", "negative": "text"})
        scene = SimpleNamespace(idx=1, narration="古代人物在屋内沉思", image_prompt="纪录片感半身镜头", image_negative="", meta_json="{}")
        provider = SimpleNamespace(id=1, base_url="https://img", default_model="flux", type="openai_compat", name="img")
        calls: list[tuple[str, str]] = []

        def _gen(**kwargs):
            calls.append((str(kwargs.get("prompt")), str(kwargs.get("negative_prompt"))))
            if len(calls) == 1:
                raise RuntimeError("timed out")
            return {"b64_json": "ZmFrZQ=="}

        image_bytes, mime, meta = generate_scene_image_via_provider(
            session=object(),
            provider=provider,
            providers=[provider],
            get_image_api_key=lambda _session, _pid: "key",
            api_key="key",
            project=project,
            pack=pack,
            scene=scene,
            openai_compat_generate_image=_gen,
        )

        self.assertEqual(len(calls), 2)
        self.assertNotEqual(calls[0][0], calls[1][0])
        self.assertEqual(calls[1][1], "")
        self.assertEqual(meta["negative_prompt"], "")
        self.assertEqual(mime, "image/png")
        self.assertTrue(image_bytes)


if __name__ == "__main__":
    unittest.main()
