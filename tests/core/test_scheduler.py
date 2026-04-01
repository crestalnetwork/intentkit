import unittest
from unittest.mock import MagicMock, patch

from intentkit.core.scheduler import create_scheduler


class TestScheduler(unittest.TestCase):
    @patch("intentkit.core.scheduler.AsyncIOScheduler")
    @patch("intentkit.core.scheduler.config")
    def test_create_scheduler_jobs_without_payment(
        self, mock_config, mock_scheduler_cls
    ):
        """When payment is disabled, only base jobs are registered."""
        mock_config.payment_enabled = False
        mock_scheduler = MagicMock()
        mock_scheduler_cls.return_value = mock_scheduler

        scheduler = create_scheduler()
        self.assertEqual(scheduler, mock_scheduler)

        calls = mock_scheduler.add_job.call_args_list
        job_ids = [c.kwargs.get("id") for c in calls]

        expected_ids = [
            "update_agent_action_cost",
            "cleanup_checkpoints",
        ]
        for job_id in expected_ids:
            self.assertIn(job_id, job_ids, f"Job {job_id} was not added to scheduler")

        # Quota jobs are disabled, payment jobs should not be present
        for absent_id in [
            "reset_daily_quotas",
            "reset_monthly_quotas",
            "refill_free_credits",
        ]:
            self.assertNotIn(absent_id, job_ids)

    @patch("intentkit.core.scheduler.AsyncIOScheduler")
    @patch("intentkit.core.scheduler.config")
    def test_create_scheduler_jobs_with_payment(self, mock_config, mock_scheduler_cls):
        """When payment is enabled, all payment-related jobs are registered."""
        mock_config.payment_enabled = True
        mock_scheduler = MagicMock()
        mock_scheduler_cls.return_value = mock_scheduler

        scheduler = create_scheduler()
        self.assertEqual(scheduler, mock_scheduler)

        calls = mock_scheduler.add_job.call_args_list
        job_ids = [c.kwargs.get("id") for c in calls]

        expected_ids = [
            "update_agent_action_cost",
            "cleanup_checkpoints",
            "refill_free_credits",
            "update_agent_account_snapshot",
            "update_agent_statistics",
            "quick_account_checks",
            "slow_account_checks",
        ]
        for job_id in expected_ids:
            self.assertIn(job_id, job_ids, f"Job {job_id} was not added to scheduler")


if __name__ == "__main__":
    unittest.main()
