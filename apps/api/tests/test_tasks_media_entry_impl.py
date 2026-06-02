import unittest

from app.tasks_media_entry_impl import autofill_media_local


class TasksMediaEntryImplTests(unittest.TestCase):
    def test_autofill_media_local_delegates_all_arguments(self):
        calls = []

        def _impl(*args, **kwargs):
            calls.append((args, kwargs))

        autofill_media_local(7, 9, prefer="image", outer_job_id=11, progress_base=20, progress_span=50, keep_running=True, media_impl=_impl)

        self.assertEqual(len(calls), 1)
        args, kwargs = calls[0]
        self.assertEqual(args, (7, 9))
        self.assertEqual(kwargs["prefer"], "image")
        self.assertEqual(kwargs["outer_job_id"], 11)
        self.assertEqual(kwargs["progress_base"], 20)
        self.assertEqual(kwargs["progress_span"], 50)
        self.assertTrue(kwargs["keep_running"])


if __name__ == "__main__":
    unittest.main()
