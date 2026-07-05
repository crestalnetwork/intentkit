import asyncio
import importlib.util
import logging
import signal
from datetime import datetime
from pathlib import Path

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
from intentkit.core.autonomous import update_autonomous_task_status
from intentkit.models.autonomous import AutonomousTaskStatus, AutonomousTaskTable
from intentkit.models.team import Team, TeamTable
from intentkit.utils.alert import cleanup_alert, send_alert
from intentkit.utils.error import IntentKitAPIError

from app.entrypoints.autonomous import run_autonomous_task

logger = logging.getLogger(__name__)

# Cache of each job's scheduling-relevant config signature, so the periodic sync
# only re-adds a job when its config actually changes. Keying on updated_at would
# re-add every job on each run, because runtime status writes bump updated_at.
autonomous_tasks_signature: dict[str, str] = {}

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
logger.info("autonomous scheduler use redis store: %s", config.redis_host)
scheduler = AsyncIOScheduler(jobstores=jobstores)

# Head job ID, it schedules the other jobs
HEAD_JOB_ID = "head"

if config.sentry_dsn:
    _ = sentry_sdk.init(
        dsn=config.sentry_dsn,
        sample_rate=config.sentry_sample_rate,
        # traces_sample_rate=config.sentry_traces_sample_rate,
        # profiles_sample_rate=config.sentry_profiles_sample_rate,
        environment=config.env,
        release=config.release,
        server_name="intent-autonomous",
    )


def _resolve_autonomous_ids_from_job(job: Job | None) -> tuple[str, str] | None:
    """Extract team_id and task_id from a scheduler job.

    Args:
        job: The APScheduler job instance, or None if job not found.

    Returns:
        A tuple of (team_id, task_id) if valid, None otherwise.
    """
    if job is None:
        return None
    if job.id in {HEAD_JOB_ID, "autonomous_heartbeat"}:
        return None
    args = job.args or ()
    if len(args) < 3:
        return None
    team_id = args[0]
    task_id = args[2]
    if not isinstance(team_id, str) or not isinstance(task_id, str):
        return None
    return team_id, task_id


async def update_autonomous_status(
    job_id: str, status: AutonomousTaskStatus | None
) -> None:
    """Update the status and next_run_time of an autonomous task in the database.

    Args:
        job_id: The APScheduler job ID (format: "{team_id}-{task_id}").
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
    team_id, task_id = resolved
    next_run_time = job.next_run_time if job else None

    # update_autonomous_task_status clears runtime state for disabled tasks, so
    # we just forward the event status and let it normalize.
    try:
        _ = await update_autonomous_task_status(team_id, task_id, status, next_run_time)
    except IntentKitAPIError:
        # Task was deleted between the event firing and this update; ignore.
        return


async def update_autonomous_status_safe(
    job_id: str, status: AutonomousTaskStatus | None
) -> None:
    """Wrapper around update_autonomous_status with error handling.

    This ensures exceptions don't get silently swallowed when called via create_task.
    """
    try:
        await update_autonomous_status(job_id, status)
    except Exception as e:
        logger.error("Failed to update autonomous status for job %s: %s", job_id, e)


def _handle_autonomous_event(
    event: JobEvent | JobSubmissionEvent | JobExecutionEvent,
) -> None:
    """Handle APScheduler job events to update autonomous task status.

    Args:
        event: The APScheduler event (submission, execution, or error).
    """
    if event.code == EVENT_JOB_SUBMITTED:
        status = AutonomousTaskStatus.RUNNING
    elif event.code == EVENT_JOB_EXECUTED:
        status = AutonomousTaskStatus.WAITING
    elif event.code == EVENT_JOB_ERROR:
        status = AutonomousTaskStatus.ERROR
    else:
        return

    _ = asyncio.create_task(update_autonomous_status_safe(event.job_id, status))


# Legacy migration coordination: the head job retries the guarded migration
# every sweep until it succeeds once; the failure alert is sent at most once.
_legacy_migration_done = False
_legacy_migration_alerted = False


async def run_legacy_autonomous_migration() -> bool:
    """Migrate legacy per-agent tasks into autonomous_tasks.

    Loads the temporary migration script by file path (scripts/ is not a
    package) and runs it only while the autonomous_tasks table is still empty,
    so every environment migrates itself on first boot of this version.
    Returns True when the table is migrated or already populated. Failures are
    logged (and alerted once) and reported as False so the head job retries on
    its next sweep instead of blocking the scheduler. Remove together with
    scripts/migrate_autonomous_to_team.py.
    """
    global _legacy_migration_alerted
    try:
        script = (
            Path(__file__).resolve().parent.parent
            / "scripts"
            / "migrate_autonomous_to_team.py"
        )
        spec = importlib.util.spec_from_file_location(
            "migrate_autonomous_to_team", script
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load migration script at {script}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _ = await module.migrate_if_table_empty()
        return True
    except Exception as e:
        logger.error("Legacy autonomous migration failed: %s", e, exc_info=True)
        if not _legacy_migration_alerted:
            _legacy_migration_alerted = True
            try:
                send_alert(f"Legacy autonomous task migration failed: {e}")
            except Exception as alert_error:
                logger.warning("Failed to send migration alert: %s", alert_error)
        return False


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
        logger.error("Error sending autonomous heartbeat: %s", e)


async def schedule_agent_autonomous_tasks():
    """
    Find all team autonomous tasks and schedule them.
    This function is called periodically to update the scheduler with new or modified tasks.
    """
    logger.info("Checking for team autonomous tasks...")

    # One-time legacy task migration; retried here until it succeeds (or the
    # table already has data). Don't schedule or prune from a possibly
    # unmigrated table — the next sweep retries in a minute.
    global _legacy_migration_done
    if not _legacy_migration_done:
        if not await run_legacy_autonomous_migration():
            return
        _legacy_migration_done = True

    # List of jobs to schedule, will delete jobs not in this list
    planned_jobs = [HEAD_JOB_ID, "autonomous_heartbeat"]

    async with get_session() as db:
        # Get all autonomous tasks whose owning team still exists.
        query = select(AutonomousTaskTable).join(
            TeamTable, TeamTable.id == AutonomousTaskTable.team_id
        )
        tasks = await db.scalars(query)
        task_rows = list(tasks)

    # Cache team owners to avoid repeated lookups within a single sweep.
    owners: dict[str, str | None] = {}

    for task in task_rows:
        if not task.enabled:
            if task.status is not None or task.next_run_time is not None:
                _ = await update_autonomous_task_status(
                    task.team_id,
                    task.id,
                    None,
                    None,
                )
            continue

        # Create a unique job ID for this autonomous task
        job_id = f"{task.team_id}-{task.id}"

        # Only re-add the job when its scheduling-relevant config changed.
        # (Runtime status/next_run_time writes bump updated_at but must NOT
        # trigger a re-add, which would churn the scheduler/Redis every run.)
        signature = "|".join(
            str(v)
            for v in (
                task.cron,
                task.prompt,
                task.enabled,
                task.target_agent_id,
            )
        )
        if autonomous_tasks_signature.get(job_id) == signature:
            # Unchanged config: keep the existing job.
            planned_jobs.append(job_id)
            continue

        if task.team_id not in owners:
            owners[task.team_id] = await Team.get_owner(task.team_id)
        owner = owners[task.team_id]
        if not owner:
            # No owner to run as: don't keep the job (let the cleanup remove it).
            logger.warning(
                "Team %s has no owner; skipping task %s", task.team_id, task.id
            )
            continue

        planned_jobs.append(job_id)

        try:
            if task.cron:
                logger.info(f"Scheduling cron task {job_id} with cron: {task.cron}")
                _ = scheduler.add_job(
                    run_autonomous_task,
                    CronTrigger.from_crontab(task.cron, timezone="UTC"),
                    id=job_id,
                    args=[
                        task.team_id,
                        owner,
                        task.id,
                        task.prompt,
                        # Placeholder for the removed has_memory slot, kept so
                        # positions line up with jobs stored before removal.
                        # Drop together with run_autonomous_task's
                        # _legacy_has_memory param after one release.
                        None,
                        task.target_agent_id,
                    ],
                    replace_existing=True,
                )
            else:
                logger.error(
                    f"Invalid autonomous configuration for task {job_id}: cron is required"
                )
        except Exception as e:
            logger.error(f"Failed to schedule autonomous task {job_id}: {e}")

        # Remember the config signature we just scheduled.
        autonomous_tasks_signature[job_id] = signature

    # Delete jobs not in the list
    logger.debug("Current jobs: %s", planned_jobs)
    jobs = scheduler.get_jobs()
    for job in jobs:
        if job.id not in planned_jobs:
            scheduler.remove_job(job.id)
            logger.info("Removed job %s", job.id)


if __name__ == "__main__":

    async def main():
        # Initialize database
        await init_db(**config.db)
        # Initialize Redis
        _ = await init_redis(
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
            _ = scheduler.add_job(
                schedule_agent_autonomous_tasks,
                "interval",
                id=HEAD_JOB_ID,
                minutes=1,
                next_run_time=datetime.now(),
                replace_existing=True,
            )

        # Add job to send heartbeat every 5 minutes
        _ = scheduler.add_job(
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
                logger.error("Error cleaning up heartbeat: %s", e)

            cleanup_alert()

        try:
            logger.info("Starting autonomous agents scheduler...")
            scheduler.start()

            # Send startup alert
            send_alert(
                f"IntentKit autonomous service started\n"
                f"env: {config.env} | release: {config.release}"
            )

            # Wait for shutdown event
            logger.info(
                "Autonomous process running. Press Ctrl+C or send SIGTERM to exit."
            )
            _ = await shutdown_event.wait()
            logger.info("Received shutdown signal. Shutting down gracefully...")
        except Exception as e:
            logger.error("Error in autonomous process: %s", e)
        finally:
            # Run the cleanup code and shutdown the scheduler
            await cleanup_resources()

            if scheduler.running:
                scheduler.shutdown()

    # Run the async main function
    asyncio.run(main())
