import unittest

from app.logging_setup import sanitize_log_text


class LoggingSetupTests(unittest.TestCase):
    def test_sanitize_log_text_masks_common_secret_shapes(self):
        raw = "api_key=sk-1234567890abcdef password='secret' Authorization: Bearer token-123 access_token=abc refresh_token=def"
        out = sanitize_log_text(raw)
        self.assertIn("api_key=***", out)
        self.assertIn("password='***", out)
        self.assertIn("Authorization: Bearer ***", out)
        self.assertIn("access_token=***", out)
        self.assertIn("refresh_token=***", out)
        self.assertNotIn("sk-1234567890abcdef", out)
        self.assertNotIn("token-123", out)


if __name__ == "__main__":
    unittest.main()
