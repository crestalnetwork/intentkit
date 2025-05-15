"""Checker for periodic read-only validation tasks.

This module runs a separate scheduler for account checks and other validation
tasks that only require read-only database access.
"""

import asyncio
import logging
import signal
import sys

import sentry_sdk
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.admin.account_checking import run_quick_checks, run_slow_checks
from app.config.config import config
from models.db import init_db
from models.redis import init_redis

logger = logging.getLogger(__name__)

if config.sentry_dsn:
    sentry_sdk.init(
        dsn=config.sentry_dsn,
        sample_rate=config.sentry_sample_rate,
        traces_sample_rate=config.sentry_traces_sample_rate,
        profiles_sample_rate=config.sentry_profiles_sample_rate,
        environment=config.env,
        release=config.release,
        server_name="intent-checker",
    )


async def run_quick_account_checks():
    """Run quick account consistency checks and send results to Slack.

    This runs the faster checks for account balances, transactions, and other credit-related consistency
    issues and reports the results to the configured Slack channel.
    """
    logger.info("Running scheduled quick account consistency checks")
    try:
        await run_quick_checks()
        logger.info("Completed quick account consistency checks")
    except Exception as e:
        logger.error(f"Error running quick account consistency checks: {e}")


async def run_slow_account_checks():
    """Run slow account consistency checks and send results to Slack.

    This runs the more resource-intensive checks for account balances, transactions,
    and other credit-related consistency issues and reports the results to the configured Slack channel.
    """
    logger.info("Running scheduled slow account consistency checks")
    try:
        await run_slow_checks()
        logger.info("Completed slow account consistency checks")
    except Exception as e:
        logger.error(f"Error running slow account consistency checks: {e}")


def create_checker():
    """Create and configure the AsyncIOScheduler for validation checks."""
    # Job Store
    jobstores = {}
    if config.redis_host:
        jobstores["default"] = RedisJobStore(
            host=config.redis_host,
            port=config.redis_port,
            jobs_key="intentkit:checker:jobs",
            run_times_key="intentkit:checker:run_times",
        )
        logger.info(f"checker using redis store: {config.redis_host}")

    scheduler = AsyncIOScheduler(jobstores=jobstores)

    # Run quick account consistency checks every 2 hours at the top of the hour
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

    return scheduler


def start_checker():
    """Create, configure and start the checker scheduler."""
    scheduler = create_checker()
    scheduler.start()
    return scheduler


if __name__ == "__main__":

    async def main():
        # Initialize database
        await init_db(**config.db)

        # Initialize Redis if configured
        if config.redis_host:
            await init_redis(
                host=config.redis_host,
                port=config.redis_port,
            )

        # Initialize checker
        scheduler = create_checker()

        # Signal handler for graceful shutdown
        def signal_handler(signum, frame):
            logger.info("Received termination signal. Shutting down gracefully...")
            scheduler.shutdown()
            sys.exit(0)

        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            logger.info("Starting checker process...")
            scheduler.start()
            # Keep the main thread running
            while True:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error in checker process: {e}")
            scheduler.shutdown()
            sys.exit(1)

    # Run the async main function
    asyncio.run(main())
