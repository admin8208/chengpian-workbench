import json
import unittest
from types import SimpleNamespace

from app.prompts.image import build_image_prompts


class ImagePromptTests(unittest.TestCase):
    def test_history_pack_does_not_force_modern_environment(self):
        pack = SimpleNamespace(key="history", config=lambda: {"style": "documentary realism", "negative": "text, watermark"})
        scene = SimpleNamespace(
            narration="皇帝停在门前，手里拿着玉玺，目光落在殿内",
            image_prompt="古代宫殿内，一名人物停在门前",
            image_negative="lowres",
            meta_json=json.dumps(
                {
                    "visual": {
                        "subject": "历史人物",
                        "setting": "古代宫殿",
                        "continuity_mode": "same_place_new_angle",
                        "camera_angle": "medium close shot",
                    },
                    "continuity": {"should_match_prev_setting": True},
                },
                ensure_ascii=False,
            ),
        )

        positive, negative = build_image_prompts(pack, scene)
        self.assertIn("Chinese historical aesthetic", positive)
        self.assertNotIn("modern Chinese environment", positive)
        self.assertIn("same room, same background identity, different framing angle", positive)
        self.assertIn("wide cinematic framing with safe side margins", positive)
        self.assertIn("text, watermark", negative)
        self.assertIn("lowres", negative)

    def test_quality_booster_and_scene_specific_direction_are_included(self):
        pack = SimpleNamespace(
            key="emotion",
            config=lambda: {
                "style": "cinematic realism",
                "negative": "watermark",
                "image_quality_booster": True,
            },
        )
        scene = SimpleNamespace(
            idx=2,
            narration="女人站在窗边压着情绪，手里捏着手机。",
            image_prompt="窗边停顿，侧脸，冷色晨光",
            image_negative="lowres",
            meta_json=json.dumps(
                {
                    "visual": {
                        "lighting": "soft morning side light",
                        "composition": "medium close-up, subject on frame right",
                        "lens_feel": "gentle push-in feeling",
                        "canonical_wardrobe": "cream knit sweater",
                        "canonical_props": ["phone", "curtain"],
                    }
                },
                ensure_ascii=False,
            ),
        )

        positive, negative = build_image_prompts(pack, scene)
        self.assertIn("masterpiece", positive)
        self.assertIn("composition: medium close-up, subject on frame right", positive)
        self.assertIn("lighting: soft morning side light", positive)
        self.assertIn("keep wardrobe consistent: cream knit sweater", positive)
        self.assertIn("keep recurring props consistent: phone, curtain", positive)
        self.assertIn("scene-specific direction: 窗边停顿，侧脸，冷色晨光", positive)
        self.assertIn("bad hands", negative)

    def test_build_image_prompts_supports_portrait_aspect(self):
        pack = SimpleNamespace(key="career", config=lambda: {"style": "cinematic realism", "negative": "text"})
        scene = SimpleNamespace(
            idx=1,
            narration="她站在楼道里沉默地看着手机。",
            image_prompt="",
            image_negative="",
            meta_json="{}",
        )

        positive, _negative = build_image_prompts(pack, scene, aspect="portrait")
        self.assertIn("vertical 9:16", positive)
        self.assertIn("tall cinematic framing with safe top and bottom margins", positive)


if __name__ == "__main__":
    unittest.main()
