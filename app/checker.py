"""Checker for periodic read-only validation tasks.

This module runs a separate scheduler for account checks and other validation
tasks that only require read-only database access.
"""

import asyncio
import logging
import signal

import sentry_sdk
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.admin.account_checking import run_quick_checks, run_slow_checks
from app.config.config import config
from models.db import init_db
from models.redis import clean_heartbeat, get_redis, init_redis, send_heartbeat

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


async def send_checker_heartbeat():
    """Send a heartbeat signal to Redis to indicate the checker is running.

    This function sends a heartbeat to Redis that expires after 16 minutes,
    allowing other services to verify that the checker is operational.
    """
    logger.info("Sending checker heartbeat")
    try:
        redis_client = get_redis()
        await send_heartbeat(redis_client, "checker")
        logger.info("Sent checker heartbeat successfully")
    except Exception as e:
        logger.error(f"Error sending checker heartbeat: {e}")


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

    # Send heartbeat every 5 minutes to indicate checker is running
    if config.redis_host:
        scheduler.add_job(
            send_checker_heartbeat,
            trigger=CronTrigger(minute="*/5", timezone="UTC"),  # Run every 5 minutes
            id="checker_heartbeat",
            name="Checker Heartbeat",
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

        # Set up a future to handle graceful shutdown
        shutdown_event = asyncio.Event()

        # Set up signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()

        # Define an async function to set the shutdown event
        async def set_shutdown():
            shutdown_event.set()

        # Register signal handlers
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(set_shutdown()))

        # Define the cleanup function that will be called on exit
        async def cleanup_resources():
            try:
                if config.redis_host:
                    redis_client = get_redis()
                    await clean_heartbeat(redis_client, "checker")
            except Exception as e:
                logger.error(f"Error cleaning up heartbeat: {e}")

        # Initialize checker
        scheduler = create_checker()

        try:
            logger.info("Starting checker process...")
            scheduler.start()

            # Wait for shutdown event
            logger.info(
                "Checker process running. Press Ctrl+C or send SIGTERM to exit."
            )
            await shutdown_event.wait()
            logger.info("Received shutdown signal. Shutting down gracefully...")
        except Exception as e:
            logger.error(f"Error in checker process: {e}")
        finally:
            # Run the cleanup code and shutdown the scheduler
            await cleanup_resources()

            if scheduler.running:
                scheduler.shutdown()

    # Run the async main function
    # We handle all signals inside the main function, so we don't need to handle KeyboardInterrupt here
    asyncio.run(main())
