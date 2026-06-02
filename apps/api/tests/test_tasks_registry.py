import unittest


class TasksRegistryTests(unittest.TestCase):
    def test_registry_loader_is_importable(self):
        from app.tasks_registry import ensure_task_registry_loaded

        self.assertIsNone(ensure_task_registry_loaded())


if __name__ == "__main__":
    unittest.main()
