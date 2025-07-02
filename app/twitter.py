import asyncio
import logging
import signal
import sys

import sentry_sdk
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.entrypoints.twitter import run_twitter_agents
from intentkit.config.config import config
from intentkit.models.db import init_db
from intentkit.models.redis import init_redis

logger = logging.getLogger(__name__)

if config.sentry_dsn:
    sentry_sdk.init(
        dsn=config.sentry_dsn,
        sample_rate=config.sentry_sample_rate,
        traces_sample_rate=config.sentry_traces_sample_rate,
        profiles_sample_rate=config.sentry_profiles_sample_rate,
        environment=config.env,
        release=config.release,
        server_name="intent-twitter",
    )

if __name__ == "__main__":

    async def main():
        # Initialize infrastructure
        await init_db(**config.db)

        # Initialize Redis if configured
        if config.redis_host:
            await init_redis(
                host=config.redis_host,
                port=config.redis_port,
            )

        # Create scheduler
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            run_twitter_agents, "interval", minutes=config.twitter_entrypoint_interval
        )

        # Register signal handlers
        def signal_handler(signum, frame):
            scheduler.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            scheduler.start()
            # Keep the main thread running
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            pass

    # Run the async main function
    asyncio.run(main())
