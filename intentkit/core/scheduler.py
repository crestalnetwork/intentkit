"""Core scheduler utilities."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping

from apscheduler.jobstores.base import BaseJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from intentkit.core.agent import (
    update_agent_action_cost,
    update_agents_account_snapshot,
    update_agents_statistics,
)
from intentkit.core.cleanup import cleanup_checkpoints
from intentkit.core.credit import refill_all_free_credits
from intentkit.models.agent_data import AgentQuota


def create_scheduler(
    jobstores: Mapping[str, BaseJobStore]
    | MutableMapping[str, BaseJobStore]
    | None = None,
) -> AsyncIOScheduler:
    """Create and configure the APScheduler with all periodic tasks."""
    scheduler = AsyncIOScheduler(jobstores=dict(jobstores or {}))

    # Reset daily quotas at UTC 00:00
    scheduler.add_job(
        AgentQuota.reset_daily_quotas,
        trigger=CronTrigger(hour=0, minute=0, timezone="UTC"),
        id="reset_daily_quotas",
        name="Reset daily quotas",
        replace_existing=True,
    )

    # Reset monthly quotas at UTC 00:00 on the first day of each month
    scheduler.add_job(
        AgentQuota.reset_monthly_quotas,
        trigger=CronTrigger(day=1, hour=0, minute=0, timezone="UTC"),
        id="reset_monthly_quotas",
        name="Reset monthly quotas",
        replace_existing=True,
    )

    # Refill free credits every hour at minute 20
    scheduler.add_job(
        refill_all_free_credits,
        trigger=CronTrigger(minute="20", timezone="UTC"),
        id="refill_free_credits",
        name="Refill free credits",
        replace_existing=True,
    )

    # Update agent account snapshots hourly
    scheduler.add_job(
        update_agents_account_snapshot,
        trigger=CronTrigger(minute=0, timezone="UTC"),
        id="update_agent_account_snapshot",
        name="Update agent account snapshots",
        replace_existing=True,
    )

    # Update agent assets daily at UTC midnight
    # This is too expensive to run daily, so it will only be triggered when detail page is visited
    # scheduler.add_job(
    #     update_agents_assets,
    #     trigger=CronTrigger(hour=0, minute=0, timezone="UTC"),
    #     id="update_agent_assets",
    #     name="Update agent assets",
    #     replace_existing=True,
    # )

    # Update agent action costs hourly at minute 40
    scheduler.add_job(
        update_agent_action_cost,
        trigger=CronTrigger(minute="40", timezone="UTC"),
        id="update_agent_action_cost",
        name="Update agent action costs",
        replace_existing=True,
    )

    # Update agent statistics daily at UTC 00:01
    scheduler.add_job(
        update_agents_statistics,
        trigger=CronTrigger(hour=0, minute=1, timezone="UTC"),
        id="update_agent_statistics",
        name="Update agent statistics",
        replace_existing=True,
    )

    # Run quick account consistency checks every 2 hours at the top of the hour
    # Run quick account consistency checks every 2 hours at the top of the hour
    from intentkit.core.account_checking import run_quick_checks, run_slow_checks

    async def run_quick_account_checks():
        """Run quick account consistency checks and send results to Slack."""
        # logger is not defined in this scope, so we use a local logger or print
        # But better to use the one from the module if we move the logger definition up or import it
        import logging

        logger = logging.getLogger(__name__)
        logger.info("Running scheduled quick account consistency checks")
        try:
            _ = await run_quick_checks()
            logger.info("Completed quick account consistency checks")
        except Exception as e:
            logger.error(f"Error running quick account consistency checks: {e}")

    async def run_slow_account_checks():
        """Run slow account consistency checks and send results to Slack."""
        import logging

        logger = logging.getLogger(__name__)
        logger.info("Running scheduled slow account consistency checks")
        try:
            _ = await run_slow_checks()
            logger.info("Completed slow account consistency checks")
        except Exception as e:
            logger.error(f"Error running slow account consistency checks: {e}")

    scheduler.add_job(
        run_quick_account_checks,
        trigger=CronTrigger(
            hour="*/2", minute="30", timezone="UTC"
        ),  # Run every 2 hours
        id="quick_account_checks",
        name="Quick Account Consistency Checks",
        replace_existing=True,
    )

    # Run slow account consistency checks once a day at midnight UTC
    scheduler.add_job(
        run_slow_account_checks,
        trigger=CronTrigger(
            hour="0,12", minute="0", timezone="UTC"
        ),  # Run 2 times a day
        id="slow_account_checks",
        name="Slow Account Consistency Checks",
        replace_existing=True,
    )

    # Cleanup old checkpoints daily at UTC 2:20
    # Cleanup old checkpoints daily at UTC 2:20

    scheduler.add_job(
        cleanup_checkpoints,
        trigger=CronTrigger(hour=2, minute=20, timezone="UTC"),
        id="cleanup_checkpoints",
        name="Cleanup old checkpoints",
        kwargs={"days": 90, "dry_run": False},
        replace_existing=True,
    )

    return scheduler
