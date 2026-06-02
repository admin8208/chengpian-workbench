import unittest

from app.services.render_defaults import default_render_dimensions, normalize_render_aspect


class RenderDefaultsTests(unittest.TestCase):
    def test_normalize_render_aspect_supports_landscape_and_portrait(self):
        self.assertEqual(normalize_render_aspect("landscape"), "landscape")
        self.assertEqual(normalize_render_aspect("portrait"), "portrait")
        self.assertEqual(normalize_render_aspect("anything-else"), "landscape")

    def test_default_render_dimensions_match_supported_project_orientations(self):
        self.assertEqual(default_render_dimensions("landscape"), (1664, 944))
        self.assertEqual(default_render_dimensions("portrait"), (944, 1664))


if __name__ == "__main__":
    unittest.main()
