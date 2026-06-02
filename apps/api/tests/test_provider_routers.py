import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from app.api.image import create_image_provider, image_status, test_image_provider as run_image_provider_test
from app.api.llm import create_llm_provider, llm_status, test_llm as run_llm_test
from app.api.media import media_providers_status, set_media_provider_key, test_media_provider as run_media_provider_test
from app.api.tts import set_tts_backend_api
from app.schemas import ImageProviderIn, ImageTestIn, LlmProviderIn, LlmTestIn, MediaKeyIn, MediaProviderTestIn
from app.schemas.tts import TtsBackendIn


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _Session:
    def __init__(self, first=None, all_rows=None):
        self.first_obj = first
        self.all_rows = all_rows or []
        self.added = []
        self.deleted = []

    def exec(self, _query):
        if self.all_rows:
            return _Rows(self.all_rows)
        return _Rows([self.first_obj] if self.first_obj is not None else [])

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)

    def flush(self):
        return None

    def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = 1


class _MultiRowsSession(_Session):
    def __init__(self, rows):
        super().__init__(all_rows=rows)

    def exec(self, _query):
        return _Rows(self.all_rows)


class ProviderRouterTests(unittest.TestCase):
    def test_llm_status_keeps_contract(self):
        provider = SimpleNamespace(id=3, name="demo", type="openai_compat", base_url="https://x", default_model="gpt")
        with patch("app.api.llm.session_scope", return_value=nullcontext(object())), patch(
            "app.api.llm.get_default_provider", return_value=provider
        ), patch("app.api.llm.has_api_key", return_value=True):
            out = llm_status()
        self.assertEqual(out.default_provider_id, 3)
        self.assertTrue(out.has_api_key)

    def test_llm_create_provider_sets_default(self):
        session = _Session()
        with patch("app.api.llm.session_scope", return_value=nullcontext(session)), patch("app.api.llm.set_default_provider") as set_default:
            out = create_llm_provider(
                LlmProviderIn(name="demo", type="ollama", base_url="http://localhost:11434", default_model="qwen", enabled=True, is_default=True)
            )
        self.assertEqual(out.name, "demo")
        set_default.assert_called_once_with(session, 1)

    def test_llm_create_provider_updates_existing_singleton(self):
        existing = SimpleNamespace(id=3, name="old", type="openai_compat", base_url="https://x", default_model="gpt", enabled=True, is_default=False, updated_at=None)
        session = _MultiRowsSession([existing])
        with patch("app.api.llm.session_scope", return_value=nullcontext(session)), patch("app.api.llm.set_default_provider") as set_default, patch(
            "app.api.llm.upsert_api_key"
        ) as upsert_api_key:
            out = create_llm_provider(
                LlmProviderIn(name="demo", type="openai_compat", base_url="https://x", default_model="gpt", enabled=True, is_default=True, api_key="sk-demo")
            )
        self.assertEqual(out.id, 3)
        self.assertEqual(existing.name, "demo")
        self.assertTrue(existing.is_default)
        upsert_api_key.assert_called_once_with(session, 3, "sk-demo")
        set_default.assert_called_once_with(session, 3)

    def test_llm_create_provider_persists_api_key_inline(self):
        session = _Session()
        with patch("app.api.llm.session_scope", return_value=nullcontext(session)), patch("app.api.llm.set_default_provider") as set_default, patch(
            "app.api.llm.upsert_api_key"
        ) as upsert_api_key:
            create_llm_provider(
                LlmProviderIn(
                    name="demo",
                    type="openai_compat",
                    base_url="https://llm",
                    default_model="gpt-4o-mini",
                    enabled=True,
                    is_default=True,
                    api_key="sk-demo",
                )
            )
        upsert_api_key.assert_called_once_with(session, 1, "sk-demo")
        set_default.assert_called_once_with(session, 1)

    def test_llm_test_reports_missing_key(self):
        session = _Session(first=SimpleNamespace(id=9, type="openai_compat", base_url="https://llm", default_model="gpt"))
        with patch("app.api.llm.session_scope", return_value=nullcontext(session)), patch("app.api.llm.get_api_key", return_value=""):
            out = run_llm_test(LlmTestIn(provider_id=9, prompt='{"ok":true}'))
        self.assertFalse(out.ok)
        self.assertEqual(out.error, "未设置 API Key")
        self.assertEqual(out.message, "测试失败：大模型鉴权失败（401），请检查 API Key。")

    def test_llm_test_uses_inline_form_values(self):
        with patch("app.api.llm.session_scope", return_value=nullcontext(_Session())), patch(
            "app.api.llm.openai_compat_chat_json", return_value={"ok": True}
        ) as chat_json:
            out = run_llm_test(
                LlmTestIn(
                    type="openai_compat",
                    base_url="https://inline-llm",
                    default_model="gpt-inline",
                    api_key="sk-inline",
                    prompt='{"ok":true}',
                )
        )
        self.assertTrue(out.ok)
        self.assertIn("测试成功：大模型可用", out.message)
        chat_json.assert_called_once()
        self.assertEqual(chat_json.call_args.kwargs["base_url"], "https://inline-llm")
        self.assertEqual(chat_json.call_args.kwargs["model"], "gpt-inline")
        self.assertEqual(chat_json.call_args.kwargs["api_key"], "sk-inline")
        self.assertEqual(chat_json.call_args.kwargs["timeout_s"], 30)
        self.assertEqual(chat_json.call_args.kwargs["max_tokens"], 128)

    def test_image_create_provider_sets_default(self):
        session = _Session()
        with patch("app.api.image.session_scope", return_value=nullcontext(session)), patch("app.api.image.set_default_image_provider") as set_default:
            out = create_image_provider(
                ImageProviderIn(name="img", type="openai_compat", base_url="https://img", default_model="flux", enabled=True, is_default=True)
            )
        self.assertEqual(out.default_model, "flux")
        set_default.assert_called_once_with(session, 1)

    def test_image_create_provider_updates_existing_singleton(self):
        existing = SimpleNamespace(id=4, name="old-img", type="openai_compat", base_url="https://img", default_model="flux", enabled=True, is_default=False, updated_at=None)
        session = _MultiRowsSession([existing])
        with patch("app.api.image.session_scope", return_value=nullcontext(session)), patch("app.api.image.set_default_image_provider") as set_default, patch(
            "app.api.image.upsert_image_api_key"
        ) as upsert_image_api_key:
            out = create_image_provider(
                ImageProviderIn(name="img", type="openai_compat", base_url="https://img", default_model="flux", enabled=True, is_default=True, api_key="img-key")
            )
        self.assertEqual(out.id, 4)
        self.assertEqual(existing.name, "img")
        self.assertTrue(existing.is_default)
        upsert_image_api_key.assert_called_once_with(session, 4, "img-key")
        set_default.assert_called_once_with(session, 4)

    def test_image_create_provider_persists_api_key_inline(self):
        session = _Session()
        with patch("app.api.image.session_scope", return_value=nullcontext(session)), patch(
            "app.api.image.set_default_image_provider"
        ) as set_default, patch("app.api.image.upsert_image_api_key") as upsert_image_api_key:
            create_image_provider(
                ImageProviderIn(
                    name="img",
                    type="openai_compat",
                    base_url="https://img",
                    default_model="flux",
                    enabled=True,
                    is_default=True,
                    api_key="img-key",
                )
            )
        upsert_image_api_key.assert_called_once_with(session, 1, "img-key")
        set_default.assert_called_once_with(session, 1)

    def test_image_test_reports_missing_key(self):
        session = _Session(first=SimpleNamespace(id=9, name="img", type="openai_compat", base_url="https://img", default_model="flux"))
        with patch("app.api.image.session_scope", return_value=nullcontext(session)), patch("app.api.image.get_image_api_key", return_value=""):
            out = run_image_provider_test(ImageTestIn(provider_id=9, prompt="desk", size="1024x1024"))
        self.assertFalse(out.ok)
        self.assertEqual(out.error, "未设置 API Key")
        self.assertEqual(out.message, "测试失败：生图模型鉴权失败（401），请检查 API Key。")

    def test_image_test_uses_inline_form_values(self):
        with patch("app.api.image.session_scope", return_value=nullcontext(_Session())), patch(
            "app.api.image.openai_compat_list_models", return_value=["flux-inline"]
        ) as list_models, patch("app.api.image.openai_compat_generate_image", return_value={"url": "https://img/out.png"}) as gen:
            out = run_image_provider_test(
                ImageTestIn(
                    base_url="https://inline-img",
                    default_model="flux-inline",
                    api_key="img-inline-key",
                    prompt="desk",
                    size="1664x944",
                )
            )
        self.assertTrue(out.ok)
        self.assertEqual(out.message, "测试成功：生图模型可用。")
        list_models.assert_called_once_with(base_url="https://inline-img", api_key="img-inline-key", timeout_s=15)
        self.assertEqual(gen.call_args.kwargs["base_url"], "https://inline-img")
        self.assertEqual(gen.call_args.kwargs["model"], "flux-inline")
        self.assertEqual(gen.call_args.kwargs["api_key"], "img-inline-key")
        self.assertEqual(gen.call_args.kwargs["size"], "1664x944")

    def test_image_test_falls_back_to_lightweight_size_when_invalid(self):
        with patch("app.api.image.session_scope", return_value=nullcontext(_Session())), patch(
            "app.api.image.openai_compat_list_models", return_value=["flux-inline"]
        ), patch("app.api.image.openai_compat_generate_image", return_value={"url": "https://img/out.png"}) as gen:
            out = run_image_provider_test(
                ImageTestIn(
                    base_url="https://inline-img",
                    default_model="flux-inline",
                    api_key="img-inline-key",
                    prompt="desk",
                    size="bad-size",
                )
            )
        self.assertTrue(out.ok)
        self.assertEqual(gen.call_args.kwargs["size"], "1024x1024")

    def test_image_test_retries_retryable_error(self):
        session = _Session(first=SimpleNamespace(id=9, name="img", type="openai_compat", base_url="https://img", default_model="flux"))
        calls = [RuntimeError('Error 520: Web server is returning an unknown error'), {"url": "https://ok"}]
        with patch("app.api.image.session_scope", return_value=nullcontext(session)), patch("app.api.image.get_image_api_key", return_value="key"), patch(
            "app.api.image.openai_compat_list_models", return_value=["flux"]
        ), patch(
            "app.api.image.openai_compat_generate_image", side_effect=calls
        ) as gen, patch("app.api.image.time.sleep"):
            out = run_image_provider_test(ImageTestIn(provider_id=9, prompt="desk", size="1024x1024"))
        self.assertTrue(out.ok)
        self.assertEqual(gen.call_count, 2)
        self.assertEqual(out.data, {"url": "https://ok"})

    def test_image_test_formats_retryable_error(self):
        session = _Session(first=SimpleNamespace(id=9, name="img", type="openai_compat", base_url="https://img", default_model="flux"))
        with patch("app.api.image.session_scope", return_value=nullcontext(session)), patch("app.api.image.get_image_api_key", return_value="key"), patch(
            "app.api.image.openai_compat_list_models", return_value=["flux"]
        ), patch(
            "app.api.image.openai_compat_generate_image", side_effect=RuntimeError('Error 520: Web server is returning an unknown error')
        ), patch("app.api.image.time.sleep"):
            out = run_image_provider_test(ImageTestIn(provider_id=9, prompt="desk", size="1024x1024"))
        self.assertFalse(out.ok)
        self.assertIn("上游生图服务暂时不稳定", out.error)
        self.assertEqual(out.message, "测试失败：上游生图服务暂时不稳定，请稍后重试。")

    def test_image_status_keeps_contract(self):
        provider = SimpleNamespace(id=7, name="img", type="openai_compat", base_url="https://img", default_model="flux")
        with patch("app.api.image.session_scope", return_value=nullcontext(object())), patch(
            "app.api.image.get_default_image_provider", return_value=provider
        ), patch("app.api.image.has_image_api_key", return_value=True):
            out = image_status()
        self.assertEqual(out.default_provider_id, 7)
        self.assertTrue(out.has_api_key)

    def test_media_status_summarizes_providers(self):
        with patch("app.api.media.session_scope", return_value=nullcontext(object())), patch(
            "app.api.media.supported_providers", return_value=["wikimedia", "pexels"]
        ), patch("app.api.media.provider_supported_kinds", side_effect=lambda p: ["image", "video"] if p == "pexels" else ["image"]), patch(
            "app.api.media.get_media_api_key", return_value="key"
        ):
            out = media_providers_status()
        self.assertEqual(out[0].provider, "wikimedia")
        self.assertIn("兜底", out[0].detail)
        self.assertEqual(out[1].detail, "已配置 · 支持 image,video")

    def test_media_status_warns_when_commercial_provider_missing(self):
        with patch("app.api.media.session_scope", return_value=nullcontext(object())), patch(
            "app.api.media.supported_providers", return_value=["pexels"]
        ), patch("app.api.media.provider_supported_kinds", return_value=["image", "video"]), patch(
            "app.api.media.get_media_api_key", return_value=""
        ):
            out = media_providers_status()
        self.assertIn("退回 Wikimedia 兜底", out[0].detail)

    def test_media_set_key_accepts_wikimedia_without_secret(self):
        out = set_media_provider_key("wikimedia", MediaKeyIn(api_key="ignored"))
        self.assertEqual(out["note"], "Wikimedia 不需要 API Key")

    def test_media_test_serializes_items(self):
        item = SimpleNamespace(
            provider="pexels",
            kind="image",
            title="cat",
            page_url="https://example.com/page",
            file_url="https://example.com/file.jpg",
            thumb_url="https://example.com/thumb.jpg",
            preview_url="https://example.com/preview.jpg",
            mime="image/jpeg",
            width=100,
            height=200,
            duration_sec=None,
            license_short="free",
            license_url="https://example.com/license",
            author="author",
            attribution="attr",
        )
        with patch("app.api.media.supported_providers", return_value=["pexels"]), patch(
            "app.api.media.provider_supports_kind", return_value=True
        ), patch("app.api.media.session_scope", return_value=nullcontext(object())), patch(
            "app.api.media.get_media_api_key", return_value="key"
        ), patch("app.api.media.search_web_media", return_value=[item]):
            out = run_media_provider_test("pexels", MediaProviderTestIn(kind="image", query="cat", limit=1))
        self.assertTrue(out.ok)
        self.assertEqual(out.items[0].title, "cat")

    def test_media_test_passes_requested_aspect(self):
        with patch("app.api.media.supported_providers", return_value=["pexels"]), patch(
            "app.api.media.provider_supports_kind", return_value=True
        ), patch("app.api.media.session_scope", return_value=nullcontext(object())), patch(
            "app.api.media.get_media_api_key", return_value="key"
        ), patch("app.api.media.search_web_media", return_value=[]) as search:
            out = run_media_provider_test("pexels", MediaProviderTestIn(kind="image", query="cat", limit=1, aspect="portrait"))
        self.assertTrue(out.ok)
        self.assertEqual(search.call_args.kwargs["aspect"], "portrait")

    def test_tts_backend_api_persists_default_voice_rate(self):
        session = _Session()
        with patch("app.api.tts.session_scope", return_value=nullcontext(session)), patch("app.api.tts.set_tts_backend"), patch(
            "app.api.tts.set_offline_voice_id"
        ), patch("app.api.tts.set_edge_voice_id"), patch("app.api.tts.set_default_voice_rate") as set_rate, patch(
            "app.api.tts.tts_status_dict",
            return_value={
                "backend": "offline_piper",
                "offline_voice_id": "zh_CN-huayan-medium",
                "edge_voice_id": "zh-CN-XiaoxiaoNeural",
                "default_voice_rate": "+10%",
                "edge_synthesis_ok": False,
                "edge_checked": False,
                "edge_detail": "",
                "offline_installed": True,
                "offline_ok": True,
                "offline_detail": "",
                "offline_installed_voice_ids": [],
                "offline_installed_voice_count": 0,
                "available_offline_voice_ids": [],
                "available_offline_voice_count": 0,
                "available_offline_voices": [],
                "available_edge_voice_ids": [],
                "available_edge_voice_count": 0,
                "available_edge_zh_cn_voice_count": 0,
                "available_edge_voices": [],
            },
        ):
            out = set_tts_backend_api(TtsBackendIn(backend="offline_piper", default_voice_rate="+10%"))
        set_rate.assert_called_once_with(session, "+10%")
        self.assertEqual(out.default_voice_rate, "+10%")


if __name__ == "__main__":
    unittest.main()
