import unittest
from unittest.mock import patch
from types import SimpleNamespace

from app import tasks_entries
from app.tasks_image_entry_impl import generate_project_images_local, generate_scene_image_local
from app.tasks import _should_generate_scene


class TasksImageEntriesTests(unittest.TestCase):
    def test_should_generate_scene_obeys_force_and_existing_asset(self):
        self.assertTrue(_should_generate_scene(scene=SimpleNamespace(image_asset_id=None), force=False))
        self.assertFalse(_should_generate_scene(scene=SimpleNamespace(image_asset_id=12), force=False))
        self.assertTrue(_should_generate_scene(scene=SimpleNamespace(image_asset_id=12), force=True))

    def test_generate_project_images_local_forwards_manage_job_state(self):
        with patch("app.tasks.generate_project_images_impl_local") as impl:
            generate_project_images_local(7, 9, force=False, manage_job_state=False)

        impl.assert_called_once_with(
            7,
            9,
            force=False,
            generate_images_impl=unittest.mock.ANY,
            manage_job_state=False,
        )

    def test_generate_scene_image_local_forwards_manage_job_state(self):
        with patch("app.tasks.generate_scene_image_impl_local") as impl:
            generate_scene_image_local(8, 12, force=True, manage_job_state=False)

        impl.assert_called_once_with(
            8,
            12,
            force=True,
            generate_images_impl=unittest.mock.ANY,
            manage_job_state=False,
        )

    def test_generate_project_images_task_forwards_manage_job_state(self):
        with patch("app.tasks_entries.generate_project_images_local") as impl:
            tasks_entries.generate_project_images.call_local(7, 9, force=False, manage_job_state=False)

        impl.assert_called_once_with(7, 9, force=False, manage_job_state=False)

    def test_generate_scene_image_task_forwards_manage_job_state(self):
        with patch("app.tasks_entries.generate_scene_image_local") as impl:
            tasks_entries.generate_scene_image.call_local(8, 12, force=True, manage_job_state=False)

        impl.assert_called_once_with(8, 12, force=True, manage_job_state=False)


if __name__ == "__main__":
    unittest.main()
