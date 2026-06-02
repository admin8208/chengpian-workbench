import unittest

from app.scene_semantics import infer_scene_semantics


class SceneTextPolicyTests(unittest.TestCase):
    def test_phone_message_scene_prefers_overlay_text_policy(self):
        sem = infer_scene_semantics(narration="她低头看着手机消息，屏幕上那句话迟迟没有发出去。", pack_key="emotion", visual_hint=None)
        policy = sem.get("text_policy") or {}
        self.assertEqual(policy.get("mode"), "overlay")
        self.assertEqual(policy.get("placement"), "top")

    def test_plain_emotion_scene_forbids_readable_text(self):
        sem = infer_scene_semantics(narration="她站在厨房门口沉默了很久，没有再说话。", pack_key="emotion", visual_hint=None)
        policy = sem.get("text_policy") or {}
        self.assertEqual(policy.get("mode"), "forbid")
        self.assertEqual(policy.get("readability"), "none")


if __name__ == "__main__":
    unittest.main()
