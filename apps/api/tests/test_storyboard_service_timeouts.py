import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.llm_client import LlmChatMessage
from app.storyboard_service import call_llm_json


class StoryboardServiceTimeoutTests(unittest.TestCase):
    def test_call_llm_json_uses_longer_timeout_for_openai_compat(self):
        provider = SimpleNamespace(type="openai_compat", base_url="https://example.com", default_model="demo-model")
        with patch("app.storyboard_service.openai_compat_chat_json", return_value={"ok": True}) as chat:
            out = call_llm_json(provider=provider, api_key="k", messages=[LlmChatMessage(role="user", content="hi")])
        self.assertEqual(out, {"ok": True})
        self.assertEqual(chat.call_args.kwargs.get("timeout_s"), 600)

    def test_call_llm_json_uses_longer_timeout_for_ollama(self):
        provider = SimpleNamespace(type="ollama", base_url="http://127.0.0.1:11434", default_model="qwen")
        with patch("app.storyboard_service.ollama_chat_json", return_value={"ok": True}) as chat:
            out = call_llm_json(provider=provider, api_key="", messages=[LlmChatMessage(role="user", content="hi")])
        self.assertEqual(out, {"ok": True})
        self.assertEqual(chat.call_args.kwargs.get("timeout_s"), 600)


if __name__ == "__main__":
    unittest.main()
