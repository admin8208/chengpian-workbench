import unittest

from app.tasks_baseline_entry_impl import prepare_project_script_local


class TasksBaselineEntryImplTests(unittest.TestCase):
    def test_prepare_project_script_local_marks_done_on_success(self):
        calls = []

        def _update_job(job_id, **kwargs):
            calls.append((job_id, kwargs))

        prepare_project_script_local(
            3,
            9,
            prepare_script_fn=lambda project_id: calls.append((project_id, {"prepared": True})),
            abort_if_job_cancelled_fn=lambda *_args, **_kwargs: False,
            update_job_fn=_update_job,
            wait_if_job_paused_fn=lambda *_args, **_kwargs: None,
        )

        self.assertTrue(any(item[0] == 3 and item[1].get("status") == "done" for item in calls if isinstance(item, tuple) and isinstance(item[1], dict)))


if __name__ == "__main__":
    unittest.main()
