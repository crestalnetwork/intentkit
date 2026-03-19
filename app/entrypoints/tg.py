import asyncio
import logging
import signal
from typing import Any

from sqlalchemy import select

from intentkit.config.config import config
from intentkit.config.db import get_session, init_db
from intentkit.config.redis import init_redis
from intentkit.models.agent import Agent, AgentTable
from intentkit.models.agent_data import AgentData
from intentkit.models.team_channel import TeamChannel, TeamChannelData, TeamChannelTable
from intentkit.utils.alert import cleanup_alert

from app.services.tg.bot.cache import (
    bot_by_token,
    get_all_team_channel_bots,
    is_agent_failed,
    is_team_channel_failed,
    team_channel_bot_by_team,
    team_channel_bot_by_token,
)
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
                select(AgentTable).where(AgentTable.telegram_entrypoint_enabled)
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
                                "there is an existing bot with %s, skipping agent %s...",
                                token,
                                agent.id,
                            )
                            continue

                        logger.info("New agent with id %s found...", agent.id)
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

        # --- Sync team channels ---
        await self._sync_team_channels()

    async def _sync_team_channels(self) -> None:
        """Sync team channel bots (Telegram).

        Handles: new channels, disabled/removed channels, and token changes.
        """
        async with get_session() as db:
            result = await db.scalars(
                select(TeamChannelTable).where(
                    TeamChannelTable.channel_type == "telegram",
                    TeamChannelTable.enabled.is_(True),
                )
            )
            team_channels = result.all()

        # Build set of active team_ids and their expected tokens
        active_teams: dict[str, str] = {}  # team_id -> token
        for item in team_channels:
            channel = TeamChannel.model_validate(item)
            if channel.config and channel.config.get("token"):
                active_teams[channel.team_id] = clean_token_str(
                    str(channel.config["token"])
                )

        # Stop bots for disabled/removed channels or changed tokens
        for token, cached_bot in list(get_all_team_channel_bots().items()):
            expected_token = active_teams.get(cached_bot.team_id)
            if expected_token is None or expected_token != token:
                logger.info(
                    "Stopping team channel bot for team %s (removed/disabled/token changed)",
                    cached_bot.team_id,
                )
                await self.bot_pool.stop_team_channel_bot(cached_bot.team_id, token)

        # Start bots for new/updated channels
        for item in team_channels:
            channel = TeamChannel.model_validate(item)
            channel_key = f"team:{channel.team_id}"
            try:
                if team_channel_bot_by_team(channel.team_id):
                    continue

                if is_team_channel_failed(channel_key):
                    logger.debug(
                        "Skipping team channel %s - in failed cache", channel_key
                    )
                    continue

                if not channel.config or not channel.config.get("token"):
                    continue

                token = clean_token_str(str(channel.config["token"]))

                if bot_by_token(token) or team_channel_bot_by_token(token):
                    logger.warning(
                        "Token already in use, skipping team channel %s", channel_key
                    )
                    continue

                logger.info("New team channel %s found...", channel_key)
                await self.bot_pool.init_team_channel_bot(channel)
                await asyncio.sleep(1)

                bot_item = team_channel_bot_by_token(token)
                if not bot_item:
                    continue
                bot_info = await bot_item.bot.get_me()
                bot_name = bot_info.first_name
                if bot_info.last_name:
                    bot_name = f"{bot_info.first_name} {bot_info.last_name}"
                data = TeamChannelData(
                    team_id=channel.team_id,
                    channel_type=channel.channel_type,
                    data={
                        "bot_id": str(bot_info.id),
                        "bot_username": bot_info.username,
                        "bot_name": bot_name,
                    },
                )
                await data.save()
            except Exception as e:
                logger.error("Failed to process team channel %s: %s", channel_key, e)

    async def start(self, interval: int):
        logger.info("New agent addition tracking started...")
        while True:
            logger.info("sync agents...")
            try:
                await self.sync()
            except Exception as e:
                logger.error("failed to sync agents: %s", e)

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
    shutdown_event = asyncio.Event()

    def signal_handler(_signum: Any, _frame: Any):
        logger.info("Received termination signal. Shutting down gracefully...")
        cleanup_alert()
        shutdown_event.set()

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

    # Keep the server running until shutdown signal
    await shutdown_event.wait()
    logging.info("Server shutdown initiated")
