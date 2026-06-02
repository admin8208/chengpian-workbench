import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.llm_client import LlmError
from app.prompts.repair import collect_bad_storyboard_scenes
from app.storyboard_postprocess import normalize_storyboard_output
from app.storyboard_service import generate_storyboard_via_llm


class StoryboardPipelineTests(unittest.TestCase):
    def test_collect_bad_storyboard_scenes_flags_invalid_rows(self):
        bad = collect_bad_storyboard_scenes(
            [
                {
                    "idx": 1,
                    "narration": "围绕主题推进情节",
                    "media_query": "办公室",
                    "search_en": "office meeting",
                    "visual_intent": {"subject": "worker", "action": "talking", "setting": "office", "time": "day", "shot": "medium"},
                }
            ]
        )
        self.assertEqual(bad[0]["idx"], 1)
        self.assertIn("narration", bad[0]["reason"])

    def test_collect_bad_storyboard_scenes_flags_missing_visual_direction_fields(self):
        bad = collect_bad_storyboard_scenes(
            [
                {
                    "idx": 1,
                    "narration": "她站在窗边看着手机。",
                    "media_query": "窗边 手机",
                    "search_en": "woman phone window",
                    "visual_intent": {"subject": "woman", "action": "looking at phone", "setting": "room window", "time": "morning", "shot": "medium"},
                }
            ]
        )
        self.assertEqual(bad[0]["idx"], 1)
        self.assertIn("visual_intent", bad[0]["reason"])

    def test_normalize_storyboard_output_sets_meta_v2(self):
        script, scenes = normalize_storyboard_output(
            obj={
                "script": "很多人不知道，测试脚本",
                "scenes": [
                    {
                        "idx": 1,
                        "narration": "其实你会发现，测试镜头",
                        "media_query": "办公室开会",
                        "search_en": "office meeting room",
                        "visual_intent": {"subject": "office worker", "action": "talking", "setting": "meeting room", "time": "day", "shot": "medium"},
                        "duration_sec": 3,
                    }
                ],
            },
            pack_key="career",
            topic="测试主题",
            base_dur=4.0,
            target_sec=8.0,
            de_ai_phrase=lambda s: s.replace("很多人不知道，", "").replace("其实你会发现，", ""),
            track_query_bias=["office overtime desk"],
            writer_name="storyboard_writer_v2",
            prompt_workflow="mix",
            default_image_prompt="b-roll, scene {idx}, {topic}",
            intent_meta={"family": "leader_communication"},
        )
        self.assertEqual(script, "测试脚本")
        self.assertEqual(scenes[0]["meta"]["prompt"]["version"], 2)
        self.assertEqual(scenes[0]["meta"]["search"]["en"], "office meeting room")
        self.assertEqual(scenes[0]["meta"]["prompt"]["material_mode"], "network")
        self.assertIn("text_policy", scenes[0]["meta"]["visual"])
        self.assertTrue(scenes[0]["meta"]["visual"]["lighting"])
        self.assertTrue(scenes[0]["meta"]["visual"]["composition"])
        self.assertTrue(scenes[0]["meta"]["visual"]["motion_intent"])

    def test_normalize_storyboard_output_ai_mode_backfills_image_prompt(self):
        _script, scenes = normalize_storyboard_output(
            obj={
                "script": "测试脚本",
                "scenes": [
                    {
                        "idx": 1,
                        "narration": "她在办公室里盯着电脑，迟迟没有打字。",
                        "visual_intent": {"subject": "office worker", "action": "typing", "setting": "office", "time": "night", "shot": "medium"},
                        "duration_sec": 3,
                    }
                ],
            },
            pack_key="career",
            topic="测试主题",
            base_dur=4.0,
            target_sec=8.0,
            de_ai_phrase=lambda s: s,
            track_query_bias=["office overtime desk"],
            writer_name="storyboard_writer_v2",
            prompt_workflow="mix",
            default_image_prompt="b-roll, scene {idx}, {topic}",
            intent_meta={"family": "leader_communication"},
            material_mode="ai",
        )
        self.assertIn("office worker", scenes[0]["image_prompt"])
        self.assertIn("office", scenes[0]["image_prompt"])
        self.assertIn("night", scenes[0]["image_prompt"])
        self.assertIn("horizontal 16:9", scenes[0]["image_prompt"])
        self.assertEqual(scenes[0]["meta"]["prompt"]["material_mode"], "ai")
        self.assertIn("text_policy", scenes[0]["meta"]["visual"])
        self.assertTrue(scenes[0]["meta"]["visual"]["lighting"])
        self.assertTrue(scenes[0]["meta"]["visual"]["composition"])
        self.assertTrue(scenes[0]["meta"]["visual"]["motion_intent"])

    def test_generate_storyboard_service_ai_mode_uses_richer_fallback_prompt(self):
        pack = SimpleNamespace(key="history", name="历史")
        provider = SimpleNamespace(type="ollama", default_model="test-model", base_url="http://localhost:11434")
        responses = [
            {
                "script": "测试脚本",
                "scenes": [
                    {"idx": 1, "narration": "线索出现", "visual_intent": {"subject": "历史人物", "action": "观察器物", "setting": "古代室内", "time": "烛光夜晚", "shot": "medium", "lighting": "warm candle light", "composition": "medium composition with object foreground", "motion_intent": "slow push in"}, "duration_sec": 3},
                ],
            }
        ]

        with patch("app.storyboard_service.ollama_chat_json", side_effect=responses):
            script, scenes = generate_storyboard_via_llm(
                topic="玉玺为什么会失踪",
                pack=pack,
                provider=provider,
                api_key="",
                character_profile="",
                workflow="mix",
                duration_profile={"scene_count": 1, "scene_duration_sec": 4.0, "target_sec": 4.0, "aspect": "landscape"},
                hook_style="sharp",
                de_ai_phrase=lambda s: s,
                material_mode="ai",
            )

        self.assertEqual(script, "测试脚本")
        prompt = scenes[0]["image_prompt"]
        self.assertIn("Chinese historical aesthetic", prompt)
        self.assertIn("wide cinematic framing with safe side margins", prompt)
        self.assertIn("古代场景", prompt)
        self.assertTrue(scenes[0]["meta"]["visual"]["lighting"])
        self.assertTrue(scenes[0]["meta"]["visual"]["composition"])
        self.assertTrue(scenes[0]["meta"]["visual"]["motion_intent"])

    def test_normalize_storyboard_output_reuses_same_entity_for_matching_subject(self):
        _script, scenes = normalize_storyboard_output(
            obj={
                "script": "测试脚本",
                "scenes": [
                    {
                        "idx": 1,
                        "narration": "皇帝站在大殿中",
                        "media_query": "皇帝大殿",
                        "search_en": "emperor palace hall",
                        "visual_intent": {"subject": "明朝皇帝 朱允炆", "action": "standing", "setting": "宫殿大殿", "time": "day", "shot": "medium"},
                        "duration_sec": 3,
                    },
                    {
                        "idx": 2,
                        "narration": "皇帝转身看向门外",
                        "media_query": "皇帝回头",
                        "search_en": "emperor turns back",
                        "visual_intent": {"subject": "朱允炆 皇帝", "action": "turning back", "setting": "大殿门口", "time": "day", "shot": "close up"},
                        "duration_sec": 3,
                    },
                ],
            },
            pack_key="history",
            topic="测试主题",
            base_dur=4.0,
            target_sec=8.0,
            de_ai_phrase=lambda s: s,
            track_query_bias=["ancient chinese palace"],
            writer_name="storyboard_writer_v2",
            prompt_workflow="mix",
            default_image_prompt="b-roll, scene {idx}, {topic}",
            intent_meta={"family": "history"},
        )
        visual1 = scenes[0]["meta"]["visual"]
        visual2 = scenes[1]["meta"]["visual"]
        self.assertEqual(visual1["subject_entity_key"], visual2["subject_entity_key"])
        self.assertEqual(visual1["canonical_subject"], visual2["canonical_subject"])
        self.assertTrue(scenes[1]["meta"]["continuity"]["should_match_prev_subject"])

    def test_normalize_storyboard_output_maps_motion_intent_from_transition_logic(self):
        _script, scenes = normalize_storyboard_output(
            obj={
                "script": "测试脚本",
                "scenes": [
                    {
                        "idx": 1,
                        "narration": "她握着手机站在窗边。",
                        "media_query": "窗边 手机",
                        "search_en": "woman phone window",
                        "visual_intent": {"subject": "woman", "action": "holding phone", "setting": "room window", "time": "morning", "shot": "medium", "continuity_mode": "same_subject_new_action"},
                        "transition_hint": "continue",
                        "duration_sec": 3,
                    },
                    {
                        "idx": 2,
                        "narration": "她把视线移开，没有回消息。",
                        "media_query": "女人 短信",
                        "search_en": "woman unread message",
                        "visual_intent": {"subject": "woman", "action": "looking away", "setting": "same room", "time": "morning", "shot": "close up", "continuity_mode": "hard_shift"},
                        "transition_hint": "cut",
                        "duration_sec": 3,
                    },
                ],
            },
            pack_key="emotion",
            topic="测试主题",
            base_dur=4.0,
            target_sec=8.0,
            de_ai_phrase=lambda s: s,
            track_query_bias=["emotion room phone"],
            writer_name="storyboard_writer_v2",
            prompt_workflow="mix",
            default_image_prompt="b-roll, scene {idx}, {topic}",
            intent_meta={"family": "emotion"},
            material_mode="ai",
        )
        self.assertEqual(scenes[0]["meta"]["visual"]["motion_intent"], "slow push in")
        self.assertEqual(scenes[1]["meta"]["visual"]["motion_intent"], "hold still")

    def test_generate_storyboard_service_runs_single_pass_flow(self):
        pack = SimpleNamespace(key="career", name="职场")
        provider = SimpleNamespace(type="ollama", default_model="test-model", base_url="http://localhost:11434")
        responses = [{
            "script": "测试脚本",
            "scenes": [
                {"idx": 1, "narration": "开场冲突", "media_query": "会议室争执", "search_en": "office argument room", "visual_intent": {"subject": "manager", "action": "arguing", "setting": "meeting room", "time": "day", "shot": "medium", "lighting": "office daylight", "composition": "medium shot, subject on frame left", "motion_intent": "slow push in"}, "duration_sec": 3},
                {"idx": 2, "narration": "升级矛盾", "media_query": "聊天记录", "search_en": "work chat screen", "visual_intent": {"subject": "employee", "action": "checking phone", "setting": "office desk", "time": "day", "shot": "close up", "lighting": "soft office desk light", "composition": "close-up with phone foreground", "motion_intent": "subtle pan right"}, "duration_sec": 3},
                {"idx": 3, "narration": "给出结论", "media_query": "复盘会议", "search_en": "team review office", "visual_intent": {"subject": "team", "action": "reviewing", "setting": "office", "time": "day", "shot": "wide", "lighting": "clean meeting room light", "composition": "wide team composition", "motion_intent": "gentle pull out"}, "duration_sec": 4},
            ],
        }]

        with patch("app.storyboard_service.ollama_chat_json", side_effect=responses):
            script, scenes = generate_storyboard_via_llm(
                topic="如何和领导对齐预期",
                pack=pack,
                provider=provider,
                api_key="",
                character_profile="",
                workflow="mix",
                duration_profile={"scene_count": 3, "scene_duration_sec": 4.0, "target_sec": 10.0},
                hook_style="sharp",
                de_ai_phrase=lambda s: s,
                material_mode="network",
            )

        self.assertEqual(script, "测试脚本")
        self.assertEqual(len(scenes), 3)
        self.assertEqual(scenes[0]["meta"]["prompt"]["writer"], "storyboard_writer_v2")

    def test_generate_storyboard_service_retries_timeout_once(self):
        pack = SimpleNamespace(key="career", name="职场")
        provider = SimpleNamespace(type="ollama", default_model="test-model", base_url="http://localhost:11434")
        responses = [
            LlmError("request timeout after 20s"),
            {
                "script": "测试脚本",
                "scenes": [
                    {"idx": 1, "narration": "开场冲突", "media_query": "会议室争执", "search_en": "office argument room", "visual_intent": {"subject": "manager", "action": "arguing", "setting": "meeting room", "time": "day", "shot": "medium", "lighting": "office daylight", "composition": "medium meeting table composition", "motion_intent": "slow push in"}, "duration_sec": 3},
                ],
            },
        ]
        with patch("app.storyboard_service.ollama_chat_json", side_effect=responses) as chat:
            script, scenes = generate_storyboard_via_llm(topic="如何和领导对齐预期", pack=pack, provider=provider, api_key="", character_profile="", workflow="mix", duration_profile={"scene_count": 1, "scene_duration_sec": 4.0, "target_sec": 4.0}, hook_style="sharp", de_ai_phrase=lambda s: s, material_mode="network")
        self.assertEqual(script, "测试脚本")
        self.assertEqual(len(scenes), 1)
        self.assertEqual(chat.call_count, 2)


if __name__ == "__main__":
    unittest.main()
    def test_generate_storyboard_service_ai_mode_supports_portrait_prompt_direction(self):
        pack = SimpleNamespace(key="history", name="历史")
        provider = SimpleNamespace(type="ollama", default_model="test-model", base_url="http://localhost:11434")
        responses = [
            {
                "script": "测试脚本",
                "scenes": [
                    {"idx": 1, "narration": "线索出现", "visual_intent": {"subject": "历史人物", "action": "观察器物", "setting": "古代室内", "time": "烛光夜晚", "shot": "medium", "lighting": "warm candle light", "composition": "medium composition with object foreground", "motion_intent": "slow push in"}, "duration_sec": 3},
                ],
            }
        ]

        with patch("app.storyboard_service.ollama_chat_json", side_effect=responses):
            script, scenes = generate_storyboard_via_llm(
                topic="玉玺为什么会失踪",
                pack=pack,
                provider=provider,
                api_key="",
                character_profile="",
                workflow="mix",
                duration_profile={"scene_count": 1, "scene_duration_sec": 4.0, "target_sec": 4.0, "aspect": "portrait"},
                hook_style="sharp",
                de_ai_phrase=lambda s: s,
                material_mode="ai",
            )

        self.assertEqual(script, "测试脚本")
        prompt = scenes[0]["image_prompt"]
        self.assertIn("vertical 9:16", prompt)
        self.assertIn("tall cinematic framing with safe top and bottom margins", prompt)
