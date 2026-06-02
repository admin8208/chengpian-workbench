import os
import unittest
from unittest.mock import patch

from app.http_client import new_session
from app.proxy_settings import detect_tts_proxy, tts_proxy_env


class ProxyIsolationTests(unittest.TestCase):
    def setUp(self):
        detect_tts_proxy.cache_clear()

    def tearDown(self):
        detect_tts_proxy.cache_clear()

    def test_new_session_does_not_inherit_global_proxy_env(self):
        with patch.dict(os.environ, {"HTTPS_PROXY": "http://127.0.0.1:17890", "HTTP_PROXY": "http://127.0.0.1:17890"}, clear=False):
            session = new_session()

        self.assertFalse(session.trust_env)
        self.assertEqual(session.proxies, {})

    def test_tts_proxy_prefers_explicit_tts_proxy(self):
        with patch.dict(os.environ, {"CHENGPIAN_TTS_PROXY": "127.0.0.1:17890"}, clear=True):
            detect_tts_proxy.cache_clear()

            self.assertEqual(detect_tts_proxy(), "http://127.0.0.1:17890")

    def test_tts_proxy_env_does_not_mutate_process_env(self):
        with patch.dict(os.environ, {"CHENGPIAN_TTS_PROXY": "http://127.0.0.1:17890"}, clear=True):
            detect_tts_proxy.cache_clear()

            self.assertEqual(tts_proxy_env()["HTTPS_PROXY"], "http://127.0.0.1:17890")
            self.assertNotIn("HTTPS_PROXY", os.environ)


if __name__ == "__main__":
    unittest.main()
