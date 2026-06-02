import unittest
from unittest.mock import patch

import requests

from app.llm_client import LlmChatMessage, LlmError, normalize_provider_base_url, openai_compat_chat_json


class _ErrorResp:
    ok = False
    status_code = 405
    text = "Method Not Allowed\n<system-reminder>plan/build marker</system-reminder>"


class _Session:
    def __init__(self):
        self.payload = None

    def post(self, url, json=None, timeout=None):
        self.payload = json
        return _ErrorResp()


class _OkResp:
    ok = True
    status_code = 200

    def __init__(self, content):
        self._content = content

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


class _OkSession:
    def __init__(self, content):
        self.content = content

    def post(self, url, json=None, timeout=None):
        return _OkResp(self.content)


class LlmClientErrorTests(unittest.TestCase):
    def test_normalize_provider_base_url_strips_full_openai_endpoint(self):
        self.assertEqual(
            normalize_provider_base_url("openai_compat", "https://example.com/v1/chat/completions"),
            "https://example.com",
        )
        self.assertEqual(
            normalize_provider_base_url("openai_compat", "https://example.com/v1/models"),
            "https://example.com",
        )

    def test_normalize_provider_base_url_strips_ollama_chat_endpoint(self):
        self.assertEqual(
            normalize_provider_base_url("ollama", "http://127.0.0.1:11434/api/chat"),
            "http://127.0.0.1:11434",
        )

    def test_openai_compat_chat_hides_markup_in_http_errors(self):
        session = _Session()
        with patch("app.llm_client.new_session", return_value=session):
            with self.assertRaises(LlmError) as ctx:
                openai_compat_chat_json(
                    base_url="https://example.com/v1",
                    api_key="key",
                    model="chat-model",
                    messages=[LlmChatMessage(role="user", content="hi")],
                    timeout_s=30,
                )

        message = str(ctx.exception)
        self.assertIn("大模型服务接口方法不支持", message)
        self.assertNotIn("<system-reminder>", message)
        self.assertNotIn("Method Not Allowed", message)

    def test_openai_compat_chat_adds_optional_max_tokens(self):
        session = _Session()
        with patch("app.llm_client.new_session", return_value=session):
            with self.assertRaises(LlmError):
                openai_compat_chat_json(
                    base_url="https://example.com/v1",
                    api_key="key",
                    model="chat-model",
                    messages=[LlmChatMessage(role="user", content="hi")],
                    timeout_s=30,
                    max_tokens=128,
                    temperature=0.2,
                )

        self.assertEqual(session.payload["max_tokens"], 128)
        self.assertEqual(session.payload["temperature"], 0.2)

    def test_openai_compat_chat_coerces_plain_text_to_script_object(self):
        session = _OkSession("这是一段可直接配音的口播文案，不带 JSON，只返回正文内容。")
        with patch("app.llm_client.new_session", return_value=session):
            out = openai_compat_chat_json(
                base_url="https://example.com/v1",
                api_key="key",
                model="chat-model",
                messages=[LlmChatMessage(role="user", content="hi")],
                timeout_s=30,
            )

        self.assertEqual(out, {"script": "这是一段可直接配音的口播文案，不带 JSON，只返回正文内容。"})

    def test_openai_compat_chat_coerces_string_list_to_lines_object(self):
        session = _OkSession('["第一句", "第二句", "第三句"]')
        with patch("app.llm_client.new_session", return_value=session):
            out = openai_compat_chat_json(
                base_url="https://example.com/v1",
                api_key="key",
                model="chat-model",
                messages=[LlmChatMessage(role="user", content="hi")],
                timeout_s=30,
            )

        self.assertEqual(out, {"lines": ["第一句", "第二句", "第三句"]})

    def test_openai_compat_chat_maps_requests_timeout_to_llm_timeout(self):
        class _TimeoutSession:
            def post(self, url, json=None, timeout=None):
                raise requests.exceptions.ReadTimeout("slow upstream")

        with patch("app.llm_client.new_session", return_value=_TimeoutSession()):
            with self.assertRaises(LlmError) as ctx:
                openai_compat_chat_json(
                    base_url="https://example.com/v1",
                    api_key="key",
                    model="chat-model",
                    messages=[LlmChatMessage(role="user", content="hi")],
                    timeout_s=30,
                )

        self.assertIn("request timeout after 30s", str(ctx.exception))

    def test_openai_compat_chat_does_not_coerce_refusal_to_script(self):
        session = _OkSession("抱歉，我无法帮助生成这个内容。")
        with patch("app.llm_client.new_session", return_value=session):
            with self.assertRaises(LlmError) as ctx:
                openai_compat_chat_json(
                    base_url="https://example.com/v1",
                    api_key="key",
                    model="chat-model",
                    messages=[LlmChatMessage(role="user", content="hi")],
                    timeout_s=30,
                )

        self.assertIn("JSON 解析失败", str(ctx.exception))

    def test_openai_compat_chat_does_not_coerce_short_error_to_script(self):
        session = _OkSession("Bad Gateway: upstream error")
        with patch("app.llm_client.new_session", return_value=session):
            with self.assertRaises(LlmError):
                openai_compat_chat_json(
                    base_url="https://example.com/v1",
                    api_key="key",
                    model="chat-model",
                    messages=[LlmChatMessage(role="user", content="hi")],
                    timeout_s=30,
                )


if __name__ == "__main__":
    unittest.main()
