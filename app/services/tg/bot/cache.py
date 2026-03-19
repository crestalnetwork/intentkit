import logging

from app.services.tg.bot.types.agent import BotPoolAgentItem
from app.services.tg.bot.types.bot import BotPoolItem
from app.services.tg.bot.types.team_channel import TeamChannelBotItem

logger = logging.getLogger(__name__)

_bots: dict[str, BotPoolItem] = {}
_agent_bots: dict[str, BotPoolAgentItem] = {}
_team_channel_bots: dict[str, TeamChannelBotItem] = {}
_failed_agents: set[str] = (
    set()
)  # Cache for agents that failed with 'Unauthorized' errors
_failed_team_channels: set[str] = set()


def bot_by_token(token: str) -> BotPoolItem | None:
    return _bots.get(token)


def set_cache_bot(bot: BotPoolItem):
    _bots[bot.token] = bot


def delete_cache_bot(token: str):
    if token in _bots:
        del _bots[token]


def agent_by_id(agent_id: str) -> BotPoolAgentItem | None:
    return _agent_bots.get(agent_id)


def set_cache_agent(agent: BotPoolAgentItem):
    _agent_bots[agent.id] = agent


def delete_cache_agent(agent_id: str):
    if agent_id in _agent_bots:
        del _agent_bots[agent_id]


def get_all_agent_bots() -> dict[str, BotPoolAgentItem]:
    return _agent_bots


def is_agent_failed(agent_id: str) -> bool:
    """Check if an agent is in the failed cache."""
    return agent_id in _failed_agents


def add_failed_agent(agent_id: str):
    """Add an agent to the failed cache."""
    _failed_agents.add(agent_id)
    logger.warning("Agent %s added to failed cache due to unauthorized error", agent_id)


def clear_failed_agents():
    """Clear the failed agents cache."""
    _failed_agents.clear()
    logger.info("Failed agents cache cleared")


# --- Team channel cache ---


def team_channel_bot_by_token(token: str) -> TeamChannelBotItem | None:
    return _team_channel_bots.get(token)


def team_channel_bot_by_team(team_id: str) -> TeamChannelBotItem | None:
    for item in _team_channel_bots.values():
        if item.team_id == team_id:
            return item
    return None


def set_cache_team_channel_bot(item: TeamChannelBotItem):
    _team_channel_bots[item.token] = item


def delete_cache_team_channel_bot(token: str):
    if token in _team_channel_bots:
        del _team_channel_bots[token]


def get_all_team_channel_bots() -> dict[str, TeamChannelBotItem]:
    return _team_channel_bots


def is_team_channel_failed(key: str) -> bool:
    return key in _failed_team_channels


def add_failed_team_channel(key: str):
    _failed_team_channels.add(key)
    logger.warning("Team channel %s added to failed cache", key)
