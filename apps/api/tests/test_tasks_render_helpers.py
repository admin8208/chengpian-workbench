import unittest
from unittest.mock import patch

from app.tasks_render_helpers import run_ffmpeg_mux_with_fallback


class TasksRenderHelpersTests(unittest.TestCase):
    def test_subtitle_burn_failure_does_not_degrade_to_audio_only(self):
        calls: list[list[str]] = []

        def fake_run_ffmpeg(args, **_kwargs):
            calls.append(list(args))
            raise RuntimeError("subtitles filter failed")

        with patch("app.tasks_render_helpers.run_ffmpeg", side_effect=fake_run_ffmpeg):
            with self.assertRaisesRegex(RuntimeError, "字幕烧录失败"):
                run_ffmpeg_mux_with_fallback(
                    ["ffmpeg", "-i", "silent.mp4", "-vf", "subtitles=bad.srt", "out.mp4"],
                    vf="subtitles=bad.srt",
                    vf_retry=None,
                    on_update=lambda **_kwargs: None,
                )

        self.assertEqual(len(calls), 1)
        self.assertIn("-vf", calls[0])

    def test_subtitle_retry_failure_does_not_degrade_to_audio_only(self):
        calls: list[list[str]] = []

        def fake_run_ffmpeg(args, **_kwargs):
            calls.append(list(args))
            raise RuntimeError("subtitles filter failed")

        with patch("app.tasks_render_helpers.run_ffmpeg", side_effect=fake_run_ffmpeg):
            with self.assertRaisesRegex(RuntimeError, "字幕烧录失败"):
                run_ffmpeg_mux_with_fallback(
                    ["ffmpeg", "-i", "silent.mp4", "-vf", "subtitles=bad.srt", "out.mp4"],
                    vf="subtitles=bad.srt",
                    vf_retry="subtitles=retry.srt",
                    on_update=lambda **_kwargs: None,
                )

        self.assertEqual(len(calls), 2)
        self.assertIn("-vf", calls[0])
        self.assertIn("-vf", calls[1])
        self.assertIn("subtitles=retry.srt", calls[1])


if __name__ == "__main__":
    unittest.main()
