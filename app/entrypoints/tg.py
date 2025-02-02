import asyncio
import logging
import signal
import sys

from sqlmodel import Session, select

from app.config.config import config
from app.services.tg.bot import pool
from app.services.tg.bot.pool import BotPool, bot_by_token
from app.services.tg.utils.cleanup import clean_token_str
from models.agent import Agent, AgentData
from models.db import get_engine, init_db

logger = logging.getLogger(__name__)


class AgentScheduler:
    def __init__(self, bot_pool: BotPool):
        self.bot_pool = bot_pool

    async def sync(self):
        with Session(get_engine()) as db:
            # Get all telegram agents
            agents = db.exec(select(Agent)).all()

            for agent in agents:
                try:
                    if agent.id not in pool._agent_bots:
                        if (
                            agent.telegram_enabled
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
                            agent_data = db.exec(
                                select(AgentData).where(AgentData.id == agent.id)
                            ).first()
                            if not agent_data:
                                agent_data = AgentData(id=agent.id)
                            agent_data.telegram_id = bot_info.id
                            agent_data.telegram_username = bot_info.username
                            agent_data.telegram_name = bot_info.first_name
                            if bot_info.last_name:
                                agent_data.telegram_name = (
                                    f"{bot_info.first_name} {bot_info.last_name}"
                                )
                            db.add(agent_data)
                            db.commit()
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


def run_telegram_server() -> None:
    # Initialize database connection
    init_db(**config.db)

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

    loop = asyncio.new_event_loop()
    loop.create_task(scheduler.start(int(config.tg_new_agent_poll_interval)))

    bot_pool.start(loop, config.tg_server_host, int(config.tg_server_port))
