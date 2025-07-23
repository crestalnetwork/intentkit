"""Scheduler for periodic tasks."""

import logging

from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.twitter.oauth2_refresh import refresh_expiring_tokens
from intentkit.config.config import config
from intentkit.core.agent import update_agent_action_cost
from intentkit.core.credit import refill_all_free_credits
from intentkit.models.agent_data import AgentQuota
from intentkit.models.redis import get_redis, send_heartbeat

logger = logging.getLogger(__name__)


async def send_scheduler_heartbeat():
    """Send a heartbeat signal to Redis to indicate the scheduler is running.

    This function sends a heartbeat to Redis that expires after 16 minutes,
    allowing other services to verify that the scheduler is operational.
    """
    logger.info("Sending scheduler heartbeat")
    try:
        redis_client = get_redis()
        await send_heartbeat(redis_client, "scheduler")
        logger.info("Sent scheduler heartbeat successfully")
    except Exception as e:
        logger.error(f"Error sending scheduler heartbeat: {e}")


def create_scheduler():
    """Create and configure the APScheduler with all periodic tasks."""
    # Job Store
    jobstores = {}
    if config.redis_host:
        jobstores["default"] = RedisJobStore(
            host=config.redis_host,
            port=config.redis_port,
            db=config.redis_db,
            jobs_key="intentkit:scheduler:jobs",
            run_times_key="intentkit:scheduler:run_times",
        )
        logger.info(f"scheduler use redis store: {config.redis_host}")

    scheduler = AsyncIOScheduler(jobstores=jobstores)

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

    # Check for expiring tokens every 5 minutes
    scheduler.add_job(
        refresh_expiring_tokens,
        trigger=CronTrigger(minute="*/5", timezone="UTC"),  # Run every 5 minutes
        id="refresh_twitter_tokens",
        name="Refresh expiring Twitter tokens",
        replace_existing=True,
    )

    # Refill free credits every 10 minutes
    scheduler.add_job(
        refill_all_free_credits,
        trigger=CronTrigger(minute="20", timezone="UTC"),  # Run every hour
        id="refill_free_credits",
        name="Refill free credits",
        replace_existing=True,
    )

    # Update agent action costs hourly
    scheduler.add_job(
        update_agent_action_cost,
        trigger=CronTrigger(minute=40, timezone="UTC"),
        id="update_agent_action_cost",
        name="Update agent action costs",
        replace_existing=True,
    )

    # Send heartbeat every minute
    if config.redis_host:
        scheduler.add_job(
            send_scheduler_heartbeat,
            trigger=CronTrigger(minute="*", timezone="UTC"),  # Run every minute
            id="scheduler_heartbeat",
            name="Scheduler Heartbeat",
            replace_existing=True,
        )

    return scheduler


def start_scheduler():
    """Create, configure and start the APScheduler."""
    scheduler = create_scheduler()
    scheduler.start()
    return scheduler
