import logging

from app.services.tg.bot.types.agent import BotPoolAgentItem
from app.services.tg.bot.types.bot import BotPoolItem

logger = logging.getLogger(__name__)

_bots: dict[str, BotPoolItem] = {}
_agent_bots: dict[str, BotPoolAgentItem] = {}
_failed_agents: set[str] = (
    set()
)  # Cache for agents that failed with 'Unauthorized' errors


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
    logger.warning(f"Agent {agent_id} added to failed cache due to unauthorized error")


def clear_failed_agents():
    """Clear the failed agents cache."""
    _failed_agents.clear()
    logger.info("Failed agents cache cleared")
