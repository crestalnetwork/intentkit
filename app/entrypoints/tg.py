import asyncio
import logging
import signal
import sys

from sqlmodel import Session, select

from app.config.config import config
from app.models.db import init_db, get_engine, Agent
from tg.bot.pool import BotPool

logger = logging.getLogger(__name__)


class AgentScheduler:
    def __init__(self, bot_pool):
        self.bot_pool = bot_pool

    def check_new_bots(self):
        with Session(get_engine()) as db:
            # Get all telegram agents
            agents = db.exec(
                select(Agent).where(
                    Agent.telegram_enabled == True,
                )
            ).all()

            new_bots = []
            for agent in agents:
                if agent.telegram_config["token"] not in self.bot_pool.bots:
                    new_bots.append(agent.telegram_config)
            return new_bots

    async def start(self, interval):
        while True:
            print("check for new bots...")
            await asyncio.sleep(interval)
            if self.check_new_bots() != None:
                for new_bot in self.check_new_bots():
                    await self.bot_pool.init_new_bot(new_bot["kind"], new_bot["token"])


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

    bot_pool = BotPool(config.tg_base_url)

    bot_pool.init_god_bot()
    bot_pool.init_all_dispatchers()

    scheduler = AgentScheduler(bot_pool)

    loop = asyncio.new_event_loop()
    loop.create_task(scheduler.start(int(config.tg_new_agent_poll_interval)))

    bot_pool.start(loop, config.tg_server_host, int(config.tg_server_port))


if __name__ == "__main__":
    run_telegram_server()