import unittest
from unittest.mock import patch

from app.tasks_image_entry_impl import generate_project_images_local, generate_scene_image_local


class TasksImageEntryImplTests(unittest.TestCase):
    def test_generate_project_images_local_fails_fast_when_cancelled(self):
        with patch("app.tasks_image_entry_impl.abort_if_job_cancelled", return_value=True), patch(
            "app.tasks_image_entry_impl.update_job"
        ) as update_job:
            generate_project_images_local(7, 9, force=False, generate_images_impl=lambda **_kwargs: None)
        update_job.assert_not_called()

    def test_generate_scene_image_local_fails_fast_when_cancelled(self):
        with patch("app.tasks_image_entry_impl.abort_if_job_cancelled", return_value=True), patch(
            "app.tasks_image_entry_impl.update_job"
        ) as update_job:
            generate_scene_image_local(8, 12, force=True, generate_images_impl=lambda **_kwargs: None)
        update_job.assert_not_called()


if __name__ == "__main__":
    unittest.main()
