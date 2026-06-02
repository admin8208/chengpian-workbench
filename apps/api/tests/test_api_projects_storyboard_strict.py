import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.modules.baseline.service import generate_storyboard_draft
from app.models import ChannelPack, Project
from app.llm_client import LlmError


class ApiProjectsStoryboardStrictTests(unittest.TestCase):
    def _project(self, *, title: str = "测试主题", source_text: str = "") -> Project:
        return Project(id=1, title=title, workflow="mix", channel_key="history", status="draft", source_text=source_text)

    def _pack(self) -> ChannelPack:
        return ChannelPack(key="history", name="历史")

    def test_generate_project_storyboard_requires_provider_even_without_source_text(self):
        with self.assertRaises(HTTPException) as ctx:
            generate_storyboard_draft(project=self._project(source_text=""), pack=self._pack(), provider=None, api_key="", render_cfg={})
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("未配置默认大模型服务", str(ctx.exception.detail))

    def test_generate_project_storyboard_timeout_no_longer_falls_back(self):
        provider = SimpleNamespace(enabled=True)
        with patch("app.modules.baseline.service.llm_generate_storyboard", side_effect=LlmError("request timeout after 20s")), patch(
            "app.modules.baseline.service.classify_llm_failure", return_value=("llm_timeout", "大模型请求超时")
        ):
            with self.assertRaises(HTTPException) as ctx:
                generate_storyboard_draft(project=self._project(source_text=""), pack=self._pack(), provider=provider, api_key="k", render_cfg={})
        self.assertEqual(ctx.exception.status_code, 502)
        self.assertIn("生成文案失败：大模型请求超时", str(ctx.exception.detail))


if __name__ == "__main__":
    unittest.main()
