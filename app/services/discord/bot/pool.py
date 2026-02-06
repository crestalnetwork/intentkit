import asyncio
import logging
from typing import Any

import discord

from intentkit.models.agent import Agent

from app.services.discord.bot.types.agent import BotPoolAgentItem
from app.services.discord.bot.types.bot import BotPoolItem

logger = logging.getLogger(__name__)

# Global caches (similar to Telegram)
# Global caches (similar to Telegram)
_bots: dict[str, BotPoolItem] = {}  # token -> BotPoolItem
_agent_bots: dict[str, BotPoolAgentItem] = {}  # agent_id -> BotPoolAgentItem
_failed_agents = set()  # Failed agent IDs
_bot_tasks: dict[str, asyncio.Task[Any]] = {}  # agent_id -> asyncio.Task


def bot_by_token(token: str) -> BotPoolItem | None:
    """Get bot by token."""
    return _bots.get(token)


def agent_by_id(agent_id: str) -> BotPoolAgentItem | None:
    """Get agent by ID."""
    return _agent_bots.get(agent_id)


def is_agent_failed(agent_id: str) -> bool:
    """Check if agent is in failed cache."""
    return agent_id in _failed_agents


def add_failed_agent(agent_id: str):
    """Add agent to failed cache."""
    _failed_agents.add(agent_id)
    logger.warning(f"Agent {agent_id} added to failed cache")


class BotPool:
    """Manages multiple Discord bot instances."""

    def __init__(self):
        pass

    async def init_new_bot(self, agent: Agent):
        """Initialize a new Discord bot for an agent."""
        bot_item = None
        try:
            bot_item = BotPoolItem(agent)
            agent_item = BotPoolAgentItem(agent)

            # Setup event handlers
            self._setup_handlers(bot_item)

            if not bot_item.token:
                raise ValueError("Bot token is empty")

            # Start bot in background task
            task = asyncio.create_task(self._run_bot(bot_item))
            _bot_tasks[agent.id] = task

            # Cache the bot
            _bots[bot_item.token] = bot_item
            _agent_bots[agent.id] = agent_item

            logger.info(f"Discord bot for agent {agent.id} initialized")

        except discord.LoginFailure as e:
            logger.error(f"Invalid Discord token for agent {agent.id}: {e}")
            add_failed_agent(agent.id)
        except Exception as e:
            logger.error(f"Failed to init Discord bot for agent {agent.id}: {e}")

    async def _run_bot(self, bot_item: BotPoolItem):
        """Run the Discord bot (blocking call)."""
        try:
            if not bot_item.token:
                raise ValueError("Token is empty")
            await bot_item.bot.start(bot_item.token)
        except Exception as e:
            logger.error(f"Bot {bot_item.agent_id} crashed: {e}")

    def _setup_handlers(self, bot_item: BotPoolItem):
        """Setup Discord event handlers."""
        from app.services.discord.bot.handlers import (
            on_message_handler,
            on_ready_handler,
        )

        @bot_item.bot.event
        async def on_ready():  # pyright: ignore[reportUnusedFunction]
            await on_ready_handler(bot_item)

        @bot_item.bot.event
        async def on_message(message: discord.Message):  # pyright: ignore[reportUnusedFunction]
            await on_message_handler(message, bot_item)

    async def stop_bot(self, agent_id: str):
        """Stop a Discord bot."""
        try:
            agent_item = agent_by_id(agent_id)
            if not agent_item or not agent_item.token:
                return

            bot_item = bot_by_token(agent_item.token)
            if bot_item and bot_item.bot:
                await bot_item.bot.close()

            # Cancel the task
            if agent_id in _bot_tasks:
                _ = _bot_tasks[agent_id].cancel()
                try:
                    await _bot_tasks[agent_id]
                except asyncio.CancelledError:
                    pass
                del _bot_tasks[agent_id]

            # Remove from caches
            if agent_item.token in _bots:
                del _bots[agent_item.token]
            if agent_id in _agent_bots:
                del _agent_bots[agent_id]

            logger.info(f"Discord bot for agent {agent_id} stopped")

        except Exception as e:
            logger.error(f"Failed to stop bot for agent {agent_id}: {e}")

    async def modify_config(self, agent: Agent):
        """Update bot configuration."""
        try:
            agent_item = agent_by_id(agent.id)
            if not agent_item or not agent_item.token:
                return

            bot_item = bot_by_token(agent_item.token)
            if bot_item:
                bot_item.update_conf(agent.discord_config or {})
                agent_item.updated_at = agent.deployed_at or agent.updated_at
                logger.info(f"Config updated for agent {agent.id}")
        except Exception as e:
            logger.error(f"Failed to update config for agent {agent.id}: {e}")
