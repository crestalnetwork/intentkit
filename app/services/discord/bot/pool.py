"""Discord bot pool management."""
import asyncio
import logging

import discord

from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData

from app.services.discord.bot.types.agent import BotPoolAgentItem
from app.services.discord.bot.types.bot import BotPoolItem

logger = logging.getLogger(__name__)

# Global caches (similar to Telegram)
_bots = {}  # token -> BotPoolItem
_agent_bots = {}  # agent_id -> BotPoolAgentItem
_failed_agents = set()  # Failed agent IDs
_bot_tasks = {}  # agent_id -> asyncio.Task


def bot_by_token(token: str) -> BotPoolItem:
    """Get bot by token."""
    return _bots.get(token)


def agent_by_id(agent_id: str) -> BotPoolAgentItem:
    """Get agent by ID."""
    return _agent_bots.get(agent_id)


def is_agent_failed(agent_id: str) -> bool:
    """Check if agent is in failed cache."""
    return agent_id in _failed_agents


def add_failed_agent(agent_id: str):
    """Add agent to failed cache."""
    _failed_agents.add(agent_id)
    logger.warning(f"Agent {agent_id} added to failed cache")


def agent_chat_id(guild_memory_public: bool, channel_id: int, guild_id: int = None):
    """
    Generate chat_id similar to Telegram pattern.
    
    Args:
        guild_memory_public: If True, share memory across guild
        channel_id: Discord channel ID
        guild_id: Discord guild/server ID
        
    Returns:
        Chat ID string for memory management
    """
    if guild_memory_public and guild_id:
        return f"discord-guild-{guild_id}"
    return f"discord-channel-{channel_id}"


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
        async def on_ready():
            await on_ready_handler(bot_item)

        @bot_item.bot.event
        async def on_message(message: discord.Message):
            await on_message_handler(message, bot_item)

    async def stop_bot(self, agent_id: str):
        """Stop a Discord bot."""
        try:
            agent_item = agent_by_id(agent_id)
            if not agent_item:
                return

            bot_item = bot_by_token(agent_item.token)
            if bot_item and bot_item.bot:
                await bot_item.bot.close()

            # Cancel the task
            if agent_id in _bot_tasks:
                _bot_tasks[agent_id].cancel()
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
            if not agent_item:
                return

            bot_item = bot_by_token(agent_item.token)
            if bot_item:
                bot_item.update_conf(agent.discord_config or {})
                agent_item.updated_at = agent.updated_at
                logger.info(f"Config updated for agent {agent.id}")
        except Exception as e:
            logger.error(f"Failed to update config for agent {agent.id}: {e}")
