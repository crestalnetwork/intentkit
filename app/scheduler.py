"""Scheduler process entry point.

This module runs the scheduler in a separate process, using the implementation
from app.admin.scheduler.
"""

import asyncio
import logging
import signal

import sentry_sdk

from app.admin.scheduler import create_scheduler
from intentkit.config.config import config
from intentkit.models.db import init_db
from intentkit.models.redis import clean_heartbeat, get_redis, init_redis

logger = logging.getLogger(__name__)

if config.sentry_dsn:
    sentry_sdk.init(
        dsn=config.sentry_dsn,
        sample_rate=config.sentry_sample_rate,
        traces_sample_rate=config.sentry_traces_sample_rate,
        profiles_sample_rate=config.sentry_profiles_sample_rate,
        environment=config.env,
        release=config.release,
        server_name="intent-scheduler",
    )


if __name__ == "__main__":

    async def main():
        # Create a shutdown event for graceful termination
        shutdown_event = asyncio.Event()

        # Initialize database
        await init_db(**config.db)

        # Initialize Redis if configured
        if config.redis_host:
            await init_redis(
                host=config.redis_host,
                port=config.redis_port,
            )

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
                    await clean_heartbeat(redis_client, "scheduler")
            except Exception as e:
                logger.error(f"Error cleaning up heartbeat: {e}")

        # Initialize scheduler
        scheduler = create_scheduler()

        try:
            logger.info("Starting scheduler process...")
            scheduler.start()

            # Wait for shutdown event
            logger.info(
                "Scheduler process running. Press Ctrl+C or send SIGTERM to exit."
            )
            await shutdown_event.wait()
            logger.info("Received shutdown signal. Shutting down gracefully...")
        except Exception as e:
            logger.error(f"Error in scheduler process: {e}")
        finally:
            # Run the cleanup code and shutdown the scheduler
            await cleanup_resources()

            if scheduler.running:
                scheduler.shutdown()

    # Run the async main function
    # We handle all signals inside the main function, so we don't need to handle KeyboardInterrupt here
    asyncio.run(main())
