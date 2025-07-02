"""Scheduler for periodic tasks."""

import logging
import time

from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, update

from app.services.twitter.oauth2_refresh import refresh_expiring_tokens
from intentkit.config.config import config
from intentkit.core.agent import agent_action_cost
from intentkit.core.credit import refill_all_free_credits
from intentkit.models.agent import AgentTable
from intentkit.models.agent_data import AgentQuotaTable
from intentkit.models.db import get_session
from intentkit.models.redis import get_redis, send_heartbeat

logger = logging.getLogger(__name__)


async def reset_daily_quotas():
    """Reset daily quotas for all agents at UTC 00:00.
    Resets message_count_daily and twitter_count_daily to 0.
    """
    async with get_session() as session:
        stmt = update(AgentQuotaTable).values(
            message_count_daily=0,
            twitter_count_daily=0,
            free_income_daily=0,
        )
        await session.execute(stmt)
        await session.commit()


async def reset_monthly_quotas():
    """Reset monthly quotas for all agents at the start of each month.
    Resets message_count_monthly and autonomous_count_monthly to 0.
    """
    async with get_session() as session:
        stmt = update(AgentQuotaTable).values(
            message_count_monthly=0, autonomous_count_monthly=0
        )
        await session.execute(stmt)
        await session.commit()


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


async def update_agent_action_cost():
    """
    Update action costs for all agents.

    This function processes agents in batches of 100 to avoid memory issues.
    For each agent, it calculates various action cost metrics:
    - avg_action_cost: average cost per action
    - min_action_cost: minimum cost per action
    - max_action_cost: maximum cost per action
    - low_action_cost: average cost of the lowest 20% of actions
    - medium_action_cost: average cost of the middle 60% of actions
    - high_action_cost: average cost of the highest 20% of actions

    It then updates the corresponding record in the agent_quotas table.
    """
    logger.info("Starting update of agent average action costs")
    start_time = time.time()
    batch_size = 100
    last_id = None
    total_updated = 0

    while True:
        # Get a batch of agent IDs ordered by ID
        async with get_session() as session:
            query = select(AgentTable.id).order_by(AgentTable.id)

            # Apply pagination if we have a last_id from previous batch
            if last_id:
                query = query.where(AgentTable.id > last_id)

            query = query.limit(batch_size)
            result = await session.execute(query)
            agent_ids = [row[0] for row in result]

            # If no more agents, we're done
            if not agent_ids:
                break

            # Update last_id for next batch
            last_id = agent_ids[-1]

        # Process this batch of agents
        logger.info(
            f"Processing batch of {len(agent_ids)} agents starting with ID {agent_ids[0]}"
        )
        batch_start_time = time.time()

        for agent_id in agent_ids:
            try:
                # Calculate action costs for this agent
                costs = await agent_action_cost(agent_id)

                # Update the agent's quota record
                async with get_session() as session:
                    update_stmt = (
                        update(AgentQuotaTable)
                        .where(AgentQuotaTable.id == agent_id)
                        .values(
                            avg_action_cost=costs["avg_action_cost"],
                            min_action_cost=costs["min_action_cost"],
                            max_action_cost=costs["max_action_cost"],
                            low_action_cost=costs["low_action_cost"],
                            medium_action_cost=costs["medium_action_cost"],
                            high_action_cost=costs["high_action_cost"],
                        )
                    )
                    await session.execute(update_stmt)
                    await session.commit()

                total_updated += 1
            except Exception as e:
                logger.error(
                    f"Error updating action costs for agent {agent_id}: {str(e)}"
                )

        batch_time = time.time() - batch_start_time
        logger.info(f"Completed batch in {batch_time:.3f}s")

    total_time = time.time() - start_time
    logger.info(
        f"Finished updating action costs for {total_updated} agents in {total_time:.3f}s"
    )


def create_scheduler():
    """Create and configure the APScheduler with all periodic tasks."""
    # Job Store
    jobstores = {}
    if config.redis_host:
        jobstores["default"] = RedisJobStore(
            host=config.redis_host,
            port=config.redis_port,
            jobs_key="intentkit:scheduler:jobs",
            run_times_key="intentkit:scheduler:run_times",
        )
        logger.info(f"scheduler use redis store: {config.redis_host}")

    scheduler = AsyncIOScheduler(jobstores=jobstores)

    # Reset daily quotas at UTC 00:00
    scheduler.add_job(
        reset_daily_quotas,
        trigger=CronTrigger(hour=0, minute=0, timezone="UTC"),
        id="reset_daily_quotas",
        name="Reset daily quotas",
        replace_existing=True,
    )

    # Reset monthly quotas at UTC 00:00 on the first day of each month
    scheduler.add_job(
        reset_monthly_quotas,
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
