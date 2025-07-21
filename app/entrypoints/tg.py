import asyncio
import logging
import signal
import sys

from sqlalchemy import select

from app.services.tg.bot import pool
from app.services.tg.bot.pool import BotPool, bot_by_token
from app.services.tg.utils.cleanup import clean_token_str
from intentkit.config.config import config
from intentkit.models.agent import Agent, AgentTable
from intentkit.models.agent_data import AgentData
from intentkit.models.db import get_session, init_db
from intentkit.models.redis import init_redis

logger = logging.getLogger(__name__)


class AgentScheduler:
    def __init__(self, bot_pool: BotPool):
        self.bot_pool = bot_pool

    async def sync(self):
        async with get_session() as db:
            # Get all telegram agents
            agents = await db.scalars(select(AgentTable))

        for item in agents:
            agent = Agent.model_validate(item)
            try:
                if agent.id not in pool._agent_bots:
                    if (
                        agent.telegram_entrypoint_enabled
                        and agent.telegram_config
                        and agent.telegram_config.get("token")
                    ):
                        token = clean_token_str(agent.telegram_config["token"])
                        if token in pool._bots:
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
                    cached_agent = pool._agent_bots[agent.id]
                    if cached_agent.updated_at != agent.updated_at:
                        if agent.telegram_config.get("token") not in pool._bots:
                            await self.bot_pool.change_bot_token(agent)
                            await asyncio.sleep(2)
                        else:
                            await self.bot_pool.modify_config(agent)
            except Exception as e:
                logger.error(
                    f"failed to process agent {agent.id}, skipping this to the next agent: {e}"
                )

    async def start(self, interval):
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

    # Initialize Redis if configured
    if config.redis_host:
        await init_redis(
            host=config.redis_host,
            port=config.redis_port,
            db=config.redis_db,
        )

    # Signal handler for graceful shutdown
    def signal_handler(signum, frame):
        logger.info("Received termination signal. Shutting down gracefully...")
        scheduler.shutdown()
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Initialize bot pool...")
    bot_pool = BotPool(config.tg_base_url)

    bot_pool.init_god_bot()
    bot_pool.init_all_dispatchers()

    scheduler = AgentScheduler(bot_pool)

    # Start the scheduler
    asyncio.create_task(scheduler.start(int(config.tg_new_agent_poll_interval)))

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
