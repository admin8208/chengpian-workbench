import unittest

from app.tasks_autopilot_entry_impl import autopilot_run_local


class TasksAutopilotEntryImplTests(unittest.TestCase):
    def test_autopilot_run_local_skips_when_guard_returns_reason(self):
        called = []

        autopilot_run_local(
            7,
            9,
            guard_reason_fn=lambda *_args, **_kwargs: "missing_job",
            acquire_job_lease=lambda *_args, **_kwargs: True,
            clear_job_lease_if_terminal=lambda *_args, **_kwargs: called.append("clear"),
            abort_if_job_cancelled=lambda *_args, **_kwargs: False,
            autopilot_run_impl=lambda *_args, **_kwargs: called.append("run"),
            fail_job=lambda *_args, **_kwargs: None,
            llm_generate_storyboard=lambda *_args, **_kwargs: None,
            llm_rewrite_storyboard=lambda *_args, **_kwargs: None,
            render_video_impl=lambda *_args, **_kwargs: None,
            autofill_media_local=lambda *_args, **_kwargs: None,
            generate_images_local=lambda *_args, **_kwargs: None,
            get_default_provider=lambda *_args, **_kwargs: None,
            get_api_key=lambda *_args, **_kwargs: "",
        )

        self.assertEqual(called, [])

    def test_autopilot_run_local_clears_lease_after_impl(self):
        called = []

        autopilot_run_local(
            7,
            9,
            guard_reason_fn=lambda *_args, **_kwargs: None,
            acquire_job_lease=lambda *_args, **_kwargs: True,
            clear_job_lease_if_terminal=lambda *_args, **_kwargs: called.append("clear"),
            abort_if_job_cancelled=lambda *_args, **_kwargs: False,
            autopilot_run_impl=lambda *_args, **_kwargs: called.append("run"),
            fail_job=lambda *_args, **_kwargs: None,
            llm_generate_storyboard=lambda *_args, **_kwargs: None,
            llm_rewrite_storyboard=lambda *_args, **_kwargs: None,
            render_video_impl=lambda *_args, **_kwargs: None,
            autofill_media_local=lambda *_args, **_kwargs: None,
            generate_images_local=lambda *_args, **_kwargs: None,
            get_default_provider=lambda *_args, **_kwargs: None,
            get_api_key=lambda *_args, **_kwargs: "",
        )

        self.assertEqual(called, ["run", "clear"])


if __name__ == "__main__":
    unittest.main()
