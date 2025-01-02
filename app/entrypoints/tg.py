import asyncio
import logging
import signal
import sys

from sqlmodel import Session, select

from app.config.config import config
from app.models.agent import Agent
from app.models.db import get_engine, init_db
from tg.bot import pool
from tg.bot.pool import BotPool

logger = logging.getLogger(__name__)


class AgentScheduler:
    def __init__(self, bot_pool):
        self.bot_pool = bot_pool

    def sync_bots(self):
        with Session(get_engine()) as db:
            # Get all telegram agents
            agents = db.exec(
                select(Agent).where(
                    Agent.telegram_enabled,
                )
            ).all()

            new_bots = []
            changed_token_bots = []
            for agent in agents:
                token = agent.telegram_config["token"]
                cfg = agent.telegram_config
                cfg["agent_id"] = agent.id

                if agent.id not in pool._agent_bots:
                    new_bots.append(cfg)
                    logger.info("New agent with id {id} found...".format(id=agent.id))
                elif token not in pool._bots:
                    changed_token_bots.append(cfg)

            return new_bots, changed_token_bots

    async def start(self, interval):
        logger.info("New agent addition tracking started...")
        while True:
            logger.info("sync bots...")
            await asyncio.sleep(interval)
            new_bots, changed_token_bots = self.sync_bots()
            if new_bots is not None:
                for new_bot in new_bots:
                    await self.bot_pool.init_new_bot(
                        new_bot["agent_id"], new_bot["kind"], new_bot["token"]
                    )
            if changed_token_bots is not None:
                for changed_bot in changed_token_bots:
                    await self.bot_pool.change_bot_token(
                        changed_bot["agent_id"], changed_bot["token"]
                    )


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


if __name__ == "__main__":
    run_telegram_server()