import asyncio
import logging

import sentry_sdk

from app.entrypoints.tg import run_telegram_server
from intentkit.config.config import config

logger = logging.getLogger(__name__)

if config.sentry_dsn:
    sentry_sdk.init(
        dsn=config.sentry_dsn,
        sample_rate=config.sentry_sample_rate,
        # traces_sample_rate=config.sentry_traces_sample_rate,
        # profiles_sample_rate=config.sentry_profiles_sample_rate,
        environment=config.env,
        release=config.release,
        server_name="intent-telegram",
    )

if __name__ == "__main__":
    asyncio.run(run_telegram_server())
