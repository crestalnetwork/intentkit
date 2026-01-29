import asyncio
import logging
import signal
from datetime import datetime

import sentry_sdk
from apscheduler.events import (
    EVENT_JOB_ERROR,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_SUBMITTED,
    JobEvent,
    JobExecutionEvent,
    JobSubmissionEvent,
)
from apscheduler.job import Job
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from intentkit.config.config import config
from intentkit.config.db import get_session, init_db
from intentkit.config.redis import (
    clean_heartbeat,
    get_redis,
    init_redis,
    send_heartbeat,
)
from intentkit.core.agent import get_agent
from intentkit.models.agent import Agent, AgentAutonomousStatus, AgentTable

from app.entrypoints.autonomous import run_autonomous_task

logger = logging.getLogger(__name__)

# Global dictionary to store task_id and last updated time
autonomous_tasks_updated_at: dict[str, datetime] = {}

# Global scheduler instance
jobstores = {
    "default": RedisJobStore(
        host=config.redis_host,
        port=config.redis_port,
        db=config.redis_db,
        password=config.redis_password,
        ssl=config.redis_ssl,
        jobs_key="intentkit:autonomous:jobs",
        run_times_key="intentkit:autonomous:run_times",
    )
}
logger.info(f"autonomous scheduler use redis store: {config.redis_host}")
scheduler = AsyncIOScheduler(jobstores=jobstores)

# Head job ID, it schedules the other jobs
HEAD_JOB_ID = "head"

if config.sentry_dsn:
    sentry_sdk.init(
        dsn=config.sentry_dsn,
        sample_rate=config.sentry_sample_rate,
        # traces_sample_rate=config.sentry_traces_sample_rate,
        # profiles_sample_rate=config.sentry_profiles_sample_rate,
        environment=config.env,
        release=config.release,
        server_name="intent-autonomous",
    )


def _resolve_autonomous_ids_from_job(job: Job | None) -> tuple[str, str] | None:
    """Extract agent_id and autonomous_id from a scheduler job.

    Args:
        job: The APScheduler job instance, or None if job not found.

    Returns:
        A tuple of (agent_id, autonomous_id) if valid, None otherwise.
    """
    if job is None:
        return None
    if job.id in {HEAD_JOB_ID, "autonomous_heartbeat"}:
        return None
    args = job.args or ()
    if len(args) < 3:
        return None
    agent_id = args[0]
    autonomous_id = args[2]
    if not isinstance(agent_id, str) or not isinstance(autonomous_id, str):
        return None
    return agent_id, autonomous_id


async def _update_autonomous_status(
    job_id: str, status: AgentAutonomousStatus | None
) -> None:
    """Update the status and next_run_time of an autonomous task in the database.

    Args:
        job_id: The APScheduler job ID (format: "{agent_id}-{autonomous_id}").
        status: The new status to set, or None to clear.

    Note:
        The next_run_time is read from the scheduler at the time this function runs.
        Due to async execution, there may be a small delay between the event firing
        and this function executing, so next_run_time reflects the state at read time.
    """
    job: Job | None = scheduler.get_job(job_id)
    resolved = _resolve_autonomous_ids_from_job(job)
    if not resolved:
        return
    agent_id, autonomous_id = resolved
    agent = await get_agent(agent_id)
    if agent is None:
        return

    tasks = agent.autonomous or []
    target = next((task for task in tasks if task.id == autonomous_id), None)
    if target is None:
        return

    next_run_time = job.next_run_time if job else None

    if target.enabled:
        updates: dict[str, AgentAutonomousStatus | datetime | None] = {
            "status": status,
            "next_run_time": next_run_time,
        }
    else:
        updates = {"status": None, "next_run_time": None}

    _ = await agent.update_autonomous_task(autonomous_id, updates)


async def _update_autonomous_status_safe(
    job_id: str, status: AgentAutonomousStatus | None
) -> None:
    """Wrapper around _update_autonomous_status with error handling.

    This ensures exceptions don't get silently swallowed when called via create_task.
    """
    try:
        await _update_autonomous_status(job_id, status)
    except Exception as e:
        logger.error(f"Failed to update autonomous status for job {job_id}: {e}")


def _handle_autonomous_event(
    event: JobEvent | JobSubmissionEvent | JobExecutionEvent,
) -> None:
    """Handle APScheduler job events to update autonomous task status.

    Args:
        event: The APScheduler event (submission, execution, or error).
    """
    if event.code == EVENT_JOB_SUBMITTED:
        status = AgentAutonomousStatus.RUNNING
    elif event.code == EVENT_JOB_EXECUTED:
        status = AgentAutonomousStatus.WAITING
    elif event.code == EVENT_JOB_ERROR:
        status = AgentAutonomousStatus.ERROR
    else:
        return

    _ = asyncio.create_task(_update_autonomous_status_safe(event.job_id, status))


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
    planned_jobs = [HEAD_JOB_ID, "autonomous_heartbeat"]

    async with get_session() as db:
        # Get all agents with autonomous configuration
        query = (
            select(AgentTable)
            .where(AgentTable.autonomous.is_not(None))
            .where(AgentTable.archived_at.is_(None))
        )
        agents = await db.scalars(query)

        for item in agents:
            agent = Agent.model_validate(item)
            if not agent.autonomous or len(agent.autonomous) == 0:
                continue

            for autonomous in agent.autonomous:
                if not autonomous.enabled:
                    if (
                        autonomous.status is not None
                        or autonomous.next_run_time is not None
                    ):
                        _ = await agent.update_autonomous_task(
                            autonomous.id,
                            {"status": None, "next_run_time": None},
                        )
                    continue

                # Create a unique task ID for this autonomous task
                task_id = f"{agent.id}-{autonomous.id}"
                planned_jobs.append(task_id)

                # Check if task exists and needs updating
                updated_at = agent.deployed_at or agent.updated_at
                if (
                    task_id in autonomous_tasks_updated_at
                    and autonomous_tasks_updated_at[task_id] >= updated_at
                ):
                    # Task exists and agent hasn't been updated, skip
                    continue

                try:
                    # Schedule new job based on minutes or cron
                    # Default has_memory to True if not set (backward compatibility)
                    task_has_memory = (
                        autonomous.has_memory
                        if autonomous.has_memory is not None
                        else True
                    )
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
                                task_has_memory,
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
                                task_has_memory,
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
                autonomous_tasks_updated_at[task_id] = (
                    agent.deployed_at or agent.updated_at
                )

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
        # Initialize Redis
        await init_redis(
            host=config.redis_host,
            port=config.redis_port,
            db=config.redis_db,
            password=config.redis_password,
            ssl=config.redis_ssl,
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
        scheduler.add_job(
            send_autonomous_heartbeat,
            trigger=CronTrigger(minute="*", timezone="UTC"),  # Run every minute
            id="autonomous_heartbeat",
            name="Autonomous Heartbeat",
            replace_existing=True,
        )

        scheduler.add_listener(
            _handle_autonomous_event,
            EVENT_JOB_SUBMITTED | EVENT_JOB_EXECUTED | EVENT_JOB_ERROR,
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
