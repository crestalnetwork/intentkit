import logging
import signal
import sys

import sentry_sdk
from apscheduler.schedulers.blocking import BlockingScheduler

from app.config.config import config
from app.entrypoints.autonomous import run_autonomous_agents
from models.db import init_db

logger = logging.getLogger(__name__)

if config.sentry_dsn:
    sentry_sdk.init(
        dsn=config.sentry_dsn,
        traces_sample_rate=config.sentry_traces_sample_rate,
        profiles_sample_rate=config.sentry_profiles_sample_rate,
        environment=config.env,
        release=config.release,
    )

if __name__ == "__main__":
    # Initialize infrastructure
    init_db(**config.db)

    # Initialize scheduler
    scheduler = BlockingScheduler()

    # Add job to run every minute
    scheduler.add_job(run_autonomous_agents, "interval", minutes=1)

    # Signal handler for graceful shutdown
    def signal_handler(signum, frame):
        logger.info("Received termination signal. Shutting down gracefully...")
        scheduler.shutdown()
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        logger.info("Starting autonomous agents scheduler...")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped. Exiting...")
