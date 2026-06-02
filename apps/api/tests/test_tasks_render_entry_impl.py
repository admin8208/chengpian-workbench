import unittest
from unittest.mock import patch

from app.tasks_render_entry_impl import render_video_local


class TasksRenderEntryImplTests(unittest.TestCase):
    def test_render_video_local_fails_fast_when_cancelled(self):
        with patch("app.tasks_render_entry_impl.abort_if_job_cancelled", return_value=True):
            called = []
            render_video_local(5, 8, render_video_impl=lambda *_args, **_kwargs: called.append(True))
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
