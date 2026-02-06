import logging

from app.services.tg.bot.cache import agent_by_id

logger = logging.getLogger(__name__)


async def has_whitelist_access(agent_id: str, chat_id: int) -> bool:
    """Check if the chat ID is whitelisted for the agent.

    If no whitelist is configured, returns True (allow all).
    """
    agent_item = agent_by_id(agent_id)
    if not agent_item:
        logger.warning(f"Agent {agent_id} not found in cache during whitelist check")
        return False

    config = agent_item.agent.telegram_config or {}
    whitelist = config.get("whitelist")

    # If whitelist is None or empty, allow all (assuming default open)
    # Adjust this logic if you want default closed.
    if not whitelist:
        return True

    if isinstance(whitelist, list):
        return chat_id in whitelist

    return False
