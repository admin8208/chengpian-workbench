import unittest
from unittest.mock import patch

from app.cleanup_utils import CleanupResult
from app.tasks_cleanup import scheduled_cleanup_task


class ScheduledCleanupTaskTests(unittest.TestCase):
    def test_scheduled_cleanup_aggregates_cleanup_result_fields(self):
        with patch("app.tasks_cleanup.cleanup_tts_cache", return_value=CleanupResult(cleaned_files=2, cleaned_bytes=3 * 1024 * 1024, errors=[])), patch(
            "app.tasks_cleanup.cleanup_temp_downloads", return_value=CleanupResult(cleaned_files=1, cleaned_bytes=1024 * 1024, errors=["temp failed"])
        ), patch(
            "app.tasks_cleanup.cleanup_orphan_files", return_value=CleanupResult(cleaned_files=4, cleaned_bytes=2 * 1024 * 1024, errors=[])
        ), patch("app.tasks_cleanup.logger.info") as info_log, patch("app.tasks_cleanup.logger.exception") as exception_log:
            scheduled_cleanup_task.call_local()

        exception_log.assert_not_called()
        self.assertTrue(any("7 files, 6.00MB freed, 1 errors" in str(call.args[0]) for call in info_log.call_args_list))


if __name__ == "__main__":
    unittest.main()
