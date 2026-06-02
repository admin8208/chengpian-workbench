import unittest
from unittest.mock import patch

from app.tasks_entries import autopilot_run, autofill_media, generate_storyboard, prepare_project_script, render_video, rewrite_storyboard


class TasksEntriesTests(unittest.TestCase):
    def test_autopilot_entry_delegates_to_local_impl(self):
        with patch("app.tasks_entries.autopilot_run_local") as local_impl:
            autopilot_run.call_local(11, 9)
        local_impl.assert_called_once_with(11, 9)

    def test_storyboard_entries_delegate_to_local_impls(self):
        with patch("app.tasks_entries.generate_storyboard_local") as storyboard_impl, patch(
            "app.tasks_entries.rewrite_storyboard_local"
        ) as rewrite_impl, patch("app.tasks_entries.prepare_project_script_local") as prepare_impl:
            generate_storyboard.call_local(3, 7, topic="x")
            rewrite_storyboard.call_local(4, 7, level="strong")
            prepare_project_script.call_local(5, 7)
        storyboard_impl.assert_called_once_with(3, 7, topic="x")
        rewrite_impl.assert_called_once_with(4, 7, level="strong")
        prepare_impl.assert_called_once()

    def test_render_and_media_entries_delegate_to_local_impls(self):
        with patch("app.tasks_entries.render_video_local") as render_impl, patch("app.tasks_entries.autofill_media_local") as media_impl:
            render_video.call_local(5, 8)
            autofill_media.call_local(7, 8, prefer="image", outer_job_id=99, progress_base=20, progress_span=50, keep_running=True)
        render_impl.assert_called_once_with(5, 8)
        media_impl.assert_called_once_with(7, 8, prefer="image", outer_job_id=99, progress_base=20, progress_span=50, keep_running=True)


if __name__ == "__main__":
    unittest.main()
