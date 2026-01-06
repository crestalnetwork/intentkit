import unittest
from unittest.mock import MagicMock, patch

from intentkit.core.credit import refill_all_free_credits
from intentkit.core.scheduler import create_scheduler
from intentkit.models.agent_data import AgentQuota


class TestScheduler(unittest.TestCase):
    @patch("intentkit.core.scheduler.AsyncIOScheduler")
    def test_create_scheduler_jobs(self, mock_scheduler_cls):
        # Setup mock instance
        mock_scheduler = MagicMock()
        mock_scheduler_cls.return_value = mock_scheduler

        # Call function
        scheduler = create_scheduler()

        # Assert returned scheduler is the mock
        self.assertEqual(scheduler, mock_scheduler)

        # Collect add_job calls
        # We can't strictly assume order, so we'll check presence of expected jobs by ID
        # add_job arguments: func, trigger=..., id=..., name=..., replace_existing=...

        calls = mock_scheduler.add_job.call_args_list
        job_ids = [c.kwargs.get("id") for c in calls]

        expected_ids = [
            "reset_daily_quotas",
            "reset_monthly_quotas",
            "refill_free_credits",
            "update_agent_account_snapshot",
            "update_agent_action_cost",
            "update_agent_statistics",
            "quick_account_checks",
            "slow_account_checks",
            "cleanup_checkpoints",
        ]

        for job_id in expected_ids:
            self.assertIn(job_id, job_ids, f"Job {job_id} was not added to scheduler")

        # Optional: Verify specific job details
        # Verify reset_daily_quotas
        self.verify_job_call(calls, "reset_daily_quotas", AgentQuota.reset_daily_quotas)

        # Verify refill_free_credits
        self.verify_job_call(calls, "refill_free_credits", refill_all_free_credits)

    def verify_job_call(self, calls, job_id, func):
        """Helper to find a call matching job_id and verify function."""
        found = False
        for c in calls:
            if c.kwargs.get("id") == job_id:
                # Arg 0 is the function
                if len(c.args) > 0:
                    self.assertEqual(c.args[0], func)
                else:
                    # Maybe passed as keyword arg 'func'? add_job signature varies but typical is first arg
                    # APScheduler add_job(func, trigger=None, args=None, kwargs=None, id=None, ...)
                    pass
                found = True
                break
        self.assertTrue(found, f"Job {job_id} call not found or malformed")


if __name__ == "__main__":
    unittest.main()
