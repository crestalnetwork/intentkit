import asyncio
import logging
import signal
import sys
from typing import Any

from sqlalchemy import select

from intentkit.config.config import config
from intentkit.config.db import get_session, init_db
from intentkit.config.redis import init_redis
from intentkit.models.agent import Agent, AgentTable
from intentkit.models.agent_data import AgentData
from intentkit.utils.alert import cleanup_alert

from app.services.tg.bot.cache import is_agent_failed
from app.services.tg.bot.pool import BotPool
from app.services.tg.utils.cleanup import clean_token_str

logger = logging.getLogger(__name__)


class AgentScheduler:
    bot_pool: BotPool

    def __init__(self, bot_pool: BotPool):
        self.bot_pool = bot_pool

    async def sync(self):
        async with get_session() as db:
            # Get only telegram-enabled agents
            agents = await db.scalars(
                select(AgentTable).where(AgentTable.telegram_entrypoint_enabled == True)
            )

        for item in agents:
            agent = Agent.model_validate(item)
            try:
                from app.services.tg.bot.cache import agent_by_id, bot_by_token

                if not agent_by_id(agent.id):
                    # Skip agents that have failed with unauthorized errors
                    if is_agent_failed(agent.id):
                        logger.debug(
                            f"Skipping agent {agent.id} - in failed cache due to unauthorized error"
                        )
                        continue

                    if agent.telegram_config and agent.telegram_config.get("token"):
                        token = clean_token_str(str(agent.telegram_config["token"]))
                        if bot_by_token(token):
                            logger.warning(
                                f"there is an existing bot with {token}, skipping agent {agent.id}..."
                            )
                            continue

                        logger.info(f"New agent with id {agent.id} found...")
                        await self.bot_pool.init_new_bot(agent)
                        await asyncio.sleep(1)
                        bot = bot_by_token(token)
                        if not bot:
                            continue
                        bot_info = await bot.bot.get_me()
                        # after bot init, refresh its info to agent data
                        agent_data = await AgentData.get(agent.id)
                        agent_data.telegram_id = str(bot_info.id)
                        agent_data.telegram_username = bot_info.username
                        agent_data.telegram_name = bot_info.first_name
                        if bot_info.last_name:
                            agent_data.telegram_name = (
                                f"{bot_info.first_name} {bot_info.last_name}"
                            )
                        await agent_data.save()
                else:
                    cached_agent = agent_by_id(agent.id)
                    if not cached_agent:
                        continue
                    updated_at = agent.deployed_at or agent.updated_at
                    if cached_agent.updated_at != updated_at:
                        token = (agent.telegram_config or {}).get("token")
                        if token and not bot_by_token(str(token)):
                            await self.bot_pool.change_bot_token(agent)
                            await asyncio.sleep(2)
                        else:
                            await self.bot_pool.modify_config(agent)
            except Exception as e:
                logger.error(
                    f"failed to process agent {agent.id}, skipping this to the next agent: {e}"
                )

    async def start(self, interval: int):
        logger.info("New agent addition tracking started...")
        while True:
            logger.info("sync agents...")
            try:
                await self.sync()
            except Exception as e:
                logger.error(f"failed to sync agents: {e}")

            await asyncio.sleep(interval)


async def run_telegram_server() -> None:
    # Initialize database connection
    await init_db(**config.db)

    # Initialize Redis
    _ = await init_redis(
        host=config.redis_host,
        port=config.redis_port,
        db=config.redis_db,
        password=config.redis_password,
        ssl=config.redis_ssl,
    )

    # Signal handler for graceful shutdown
    def signal_handler(_signum: Any, _frame: Any):
        logger.info("Received termination signal. Shutting down gracefully...")
        cleanup_alert()
        sys.exit(0)

    # Register signal handlers
    _ = signal.signal(signal.SIGINT, signal_handler)
    _ = signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Initialize bot pool...")
    bot_pool = BotPool(config.tg_base_url or "")

    bot_pool.init_god_bot()
    bot_pool.init_all_dispatchers()

    scheduler = AgentScheduler(bot_pool)

    # Start the scheduler
    _ = asyncio.create_task(scheduler.start(int(config.tg_new_agent_poll_interval)))

    # Start the bot pool
    await bot_pool.start(
        asyncio.get_running_loop(), config.tg_server_host, int(config.tg_server_port)
    )

    # Keep the server running
    try:
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour
    except asyncio.CancelledError:
        logging.info("Server shutdown initiated")
        cleanup_alert()
