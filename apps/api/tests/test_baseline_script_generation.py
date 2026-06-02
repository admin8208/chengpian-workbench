import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.modules.baseline.service import llm_generate_script_draft


class BaselineScriptGenerationTests(unittest.TestCase):
    def test_script_draft_accepts_script_only_json(self):
        provider = SimpleNamespace(type="openai_compat", default_model="m")
        pack = SimpleNamespace(key="history", name="历史")

        with patch("app.modules.baseline.service.call_llm_json", return_value={"script": "这是一段口播文案。"}) as call_llm:
            script = llm_generate_script_draft(
                title="威武大将军之死",
                source_text="",
                pack=pack,
                provider=provider,
                api_key="k",
                render_cfg={"target_sec": 30},
            )

        self.assertEqual(script, "这是一段口播文案。")
        messages = call_llm.call_args.kwargs["messages"]
        self.assertIn("不生成分镜", messages[0].content)
        self.assertIn("不要输出 scenes", messages[0].content)
        self.assertEqual(call_llm.call_args.kwargs["timeout_s"], 120)
        self.assertGreaterEqual(call_llm.call_args.kwargs["max_tokens"], 384)


if __name__ == "__main__":
    unittest.main()
