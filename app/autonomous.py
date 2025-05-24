import asyncio
import logging
import signal
from datetime import datetime
from typing import Dict

import sentry_sdk
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.config.config import config
from app.entrypoints.autonomous import run_autonomous_task
from models.agent import Agent, AgentTable
from models.db import get_session, init_db
from models.redis import clean_heartbeat, get_redis, init_redis, send_heartbeat

logger = logging.getLogger(__name__)

# Global dictionary to store task_id and last updated time
autonomous_tasks_updated_at: Dict[str, datetime] = {}

# Global scheduler instance
jobstores = {}
if config.redis_host:
    jobstores["default"] = RedisJobStore(
        host=config.redis_host,
        port=config.redis_port,
        jobs_key="intentkit:autonomous:jobs",
        run_times_key="intentkit:autonomous:run_times",
    )
    logger.info(f"autonomous scheduler use redis store: {config.redis_host}")
scheduler = AsyncIOScheduler(jobstores=jobstores)

# Head job ID, it schedules the other jobs
HEAD_JOB_ID = "head"


if config.sentry_dsn:
    sentry_sdk.init(
        dsn=config.sentry_dsn,
        sample_rate=config.sentry_sample_rate,
        traces_sample_rate=config.sentry_traces_sample_rate,
        profiles_sample_rate=config.sentry_profiles_sample_rate,
        environment=config.env,
        release=config.release,
        server_name="intent-autonomous",
    )


async def send_autonomous_heartbeat():
    """Send a heartbeat signal to Redis to indicate the autonomous service is running.

    This function sends a heartbeat to Redis that expires after 16 minutes,
    allowing other services to verify that the autonomous service is operational.
    """
    logger.info("Sending autonomous heartbeat")
    try:
        redis_client = get_redis()
        await send_heartbeat(redis_client, "autonomous")
        logger.info("Sent autonomous heartbeat successfully")
    except Exception as e:
        logger.error(f"Error sending autonomous heartbeat: {e}")


async def schedule_agent_autonomous_tasks():
    """
    Find all agents with autonomous tasks and schedule them.
    This function is called periodically to update the scheduler with new or modified tasks.
    """
    logger.info("Checking for agent autonomous tasks...")

    # List of jobs to schedule, will delete jobs not in this list
    planned_jobs = [HEAD_JOB_ID]

    async with get_session() as db:
        # Get all agents with autonomous configuration
        query = select(AgentTable).where(AgentTable.autonomous != None)  # noqa: E711
        agents = await db.scalars(query)

        for item in agents:
            agent = Agent.model_validate(item)
            if not agent.autonomous or len(agent.autonomous) == 0:
                continue

            for autonomous in agent.autonomous:
                if not autonomous.enabled:
                    continue

                # Create a unique task ID for this autonomous task
                task_id = f"{agent.id}-{autonomous.id}"
                planned_jobs.append(task_id)

                # Check if task exists and needs updating
                if (
                    task_id in autonomous_tasks_updated_at
                    and autonomous_tasks_updated_at[task_id] >= agent.updated_at
                ):
                    # Task exists and agent hasn't been updated, skip
                    continue

                try:
                    # Schedule new job based on minutes or cron
                    if autonomous.cron:
                        logger.info(
                            f"Scheduling cron task {task_id} with cron: {autonomous.cron}"
                        )
                        scheduler.add_job(
                            run_autonomous_task,
                            CronTrigger.from_crontab(autonomous.cron),
                            id=task_id,
                            args=[
                                agent.id,
                                agent.owner,
                                autonomous.id,
                                autonomous.prompt,
                            ],
                            replace_existing=True,
                        )
                    elif autonomous.minutes:
                        logger.info(
                            f"Scheduling interval task {task_id} every {autonomous.minutes} minutes"
                        )
                        scheduler.add_job(
                            run_autonomous_task,
                            "interval",
                            id=task_id,
                            args=[
                                agent.id,
                                agent.owner,
                                autonomous.id,
                                autonomous.prompt,
                            ],
                            minutes=autonomous.minutes,
                            replace_existing=True,
                        )
                    else:
                        logger.error(
                            f"Invalid autonomous configuration for task {task_id}: {autonomous}"
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to schedule autonomous task [{agent.id}] {task_id}: {e}"
                    )

                # Update the last updated time
                autonomous_tasks_updated_at[task_id] = agent.updated_at

    # Delete jobs not in the list
    logger.debug(f"Current jobs: {planned_jobs}")
    jobs = scheduler.get_jobs()
    for job in jobs:
        if job.id not in planned_jobs:
            scheduler.remove_job(job.id)
            logger.info(f"Removed job {job.id}")


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

        # Add job to schedule agent autonomous tasks every 5 minutes
        # Run it immediately on startup and then every 5 minutes
        jobs = scheduler.get_jobs()
        job_ids = [job.id for job in jobs]
        if HEAD_JOB_ID not in job_ids:
            scheduler.add_job(
                schedule_agent_autonomous_tasks,
                "interval",
                id=HEAD_JOB_ID,
                minutes=1,
                next_run_time=datetime.now(),
                replace_existing=True,
            )

        # Add job to send heartbeat every 5 minutes
        if config.redis_host:
            scheduler.add_job(
                send_autonomous_heartbeat,
                "interval",
                id="autonomous_heartbeat",
                minutes=5,
                next_run_time=datetime.now(),
                replace_existing=True,
            )

        # Create a shutdown event for graceful termination
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
                    await clean_heartbeat(redis_client, "autonomous")
            except Exception as e:
                logger.error(f"Error cleaning up heartbeat: {e}")

        try:
            logger.info("Starting autonomous agents scheduler...")
            scheduler.start()

            # Wait for shutdown event
            logger.info(
                "Autonomous process running. Press Ctrl+C or send SIGTERM to exit."
            )
            await shutdown_event.wait()
            logger.info("Received shutdown signal. Shutting down gracefully...")
        except Exception as e:
            logger.error(f"Error in autonomous process: {e}")
        finally:
            # Run the cleanup code and shutdown the scheduler
            await cleanup_resources()

            if scheduler.running:
                scheduler.shutdown()

    # Run the async main function
    asyncio.run(main())
