import unittest
from unittest.mock import patch

from app.llm_client import openai_compat_generate_image


class _Resp:
    ok = True

    def json(self):
        return {"created": 1, "data": [{"b64_json": "ZmFrZQ=="}]}


class _Session:
    def __init__(self):
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return _Resp()


class LlmClientImageFormatTests(unittest.TestCase):
    def test_openai_compat_generate_image_requests_b64_json(self):
        session = _Session()
        with patch("app.llm_client.new_session", return_value=session):
            out = openai_compat_generate_image(
                base_url="https://example.com/v1",
                api_key="key",
                model="img-model",
                prompt="desk",
                size="512x512",
                timeout_s=30,
            )

        self.assertEqual(session.calls[0]["json"]["response_format"], "b64_json")
        self.assertTrue(out["has_b64"])

    def test_openai_compat_generate_image_sends_negative_prompt_when_present(self):
        session = _Session()
        with patch("app.llm_client.new_session", return_value=session):
            openai_compat_generate_image(
                base_url="https://example.com/v1",
                api_key="key",
                model="img-model",
                prompt="desk",
                negative_prompt="text, watermark",
                size="512x512",
                timeout_s=30,
            )

        self.assertEqual(session.calls[0]["json"]["negative_prompt"], "text, watermark")


if __name__ == "__main__":
    unittest.main()
