"""Discord entrypoint for IntentKit."""

import asyncio
import logging
import signal
import sys

from sqlalchemy import select

from intentkit.config.config import config
from intentkit.config.db import get_session, init_db
from intentkit.config.redis import init_redis
from intentkit.models.agent import Agent, AgentTable
from intentkit.utils.alert import cleanup_alert

from app.services.discord.bot import pool as pool_module
from app.services.discord.bot.pool import BotPool, agent_by_id, is_agent_failed

logger = logging.getLogger(__name__)


class AgentScheduler:
    """Syncs Discord-enabled agents from database (similar to Telegram)."""

    def __init__(self, bot_pool: BotPool):
        self.bot_pool = bot_pool

    async def sync(self):
        """Sync agents from database."""
        async with get_session() as db:
            # Get only discord-enabled agents
            agents = await db.scalars(
                select(AgentTable).where(AgentTable.discord_entrypoint_enabled)
            )

        for item in agents:
            agent = Agent.model_validate(item)
            try:
                if agent.id not in pool_module._agent_bots:
                    # Skip failed agents
                    if is_agent_failed(agent.id):
                        logger.debug(
                            f"Skipping agent {agent.id} - in failed cache due to unauthorized error"
                        )
                        continue

                    if agent.discord_config and agent.discord_config.get("token"):
                        logger.info(f"New Discord agent {agent.id} found")
                        await self.bot_pool.init_new_bot(agent)
                        await asyncio.sleep(1)
                else:
                    # Check for updates
                    cached = agent_by_id(agent.id)
                    updated_at = agent.deployed_at or agent.updated_at
                    if cached.updated_at != updated_at:
                        if not agent.discord_entrypoint_enabled:
                            await self.bot_pool.stop_bot(agent.id)
                        else:
                            await self.bot_pool.modify_config(agent)

            except Exception as e:
                logger.error(
                    f"Failed to process agent {agent.id}, skipping to next agent: {e}"
                )

    async def start(self, interval: int):
        """Start the scheduler."""
        logger.info("Discord agent scheduler started")
        while True:
            logger.info("Syncing Discord agents...")
            try:
                await self.sync()
            except Exception as e:
                logger.error(f"Failed to sync agents: {e}")

            await asyncio.sleep(interval)


async def run_discord_server() -> None:
    """Main Discord server entrypoint."""
    # Initialize database connection
    await init_db(**config.db)

    # Initialize Redis
    await init_redis(
        host=config.redis_host,
        port=config.redis_port,
        db=config.redis_db,
        password=config.redis_password,
        ssl=config.redis_ssl,
    )

    # Signal handler for graceful shutdown
    def signal_handler(signum, frame):
        logger.info("Received termination signal. Shutting down gracefully...")
        cleanup_alert()
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Initializing Discord bot pool...")
    bot_pool = BotPool()

    scheduler = AgentScheduler(bot_pool)

    # Start the scheduler
    asyncio.create_task(scheduler.start(int(config.discord_new_agent_poll_interval)))

    # Keep the server running
    try:
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour
    except asyncio.CancelledError:
        logger.info("Discord server shutdown initiated")
        cleanup_alert()
