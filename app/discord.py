"""Discord bot runner for IntentKit."""
import asyncio
import logging

import sentry_sdk

from intentkit.config.config import config

from app.entrypoints.discord import run_discord_server

logger = logging.getLogger(__name__)

if config.sentry_dsn:
    sentry_sdk.init(
        dsn=config.sentry_dsn,
        sample_rate=config.sentry_sample_rate,
        environment=config.env,
        release=config.release,
        server_name="intent-discord",
    )

if __name__ == "__main__":
    asyncio.run(run_discord_server())
