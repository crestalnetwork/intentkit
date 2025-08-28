"""Chat memory management utilities.

This module provides functions for managing chat thread memory,
including clearing thread history using LangGraph's checkpointer.
"""

import logging

from intentkit.models.db import get_langgraph_checkpointer
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


async def clear_thread_memory(agent_id: str, chat_id: str) -> bool:
    """Clear all memory content for a specific thread.

    This function uses LangGraph's official checkpointer.delete_thread() method
    to permanently remove all stored checkpoints and conversation history
    associated with the specified thread.

    Args:
        agent_id (str): The agent identifier
        chat_id (str): The chat identifier

    Returns:
        bool: True if the thread memory was successfully cleared

    Raises:
        IntentKitAPIError: If there's an error clearing the thread memory
    """
    try:
        # Construct thread_id by combining agent_id and chat_id
        thread_id = f"{agent_id}_{chat_id}"

        # Get the LangGraph checkpointer instance
        checkpointer = get_langgraph_checkpointer()

        # Use the official LangGraph method to delete all thread content
        await checkpointer.delete_thread(thread_id)

        logger.info(f"Successfully cleared thread memory for thread_id: {thread_id}")
        return True

    except Exception as e:
        logger.error(
            f"Failed to clear thread memory for agent_id: {agent_id}, chat_id: {chat_id}. Error: {str(e)}"
        )
        raise IntentKitAPIError(
            500, "ThreadMemoryClearError", f"Failed to clear thread memory: {str(e)}"
        )
