"""Chat memory management utilities.

This module provides functions for managing chat thread memory,
including clearing thread history by directly deleting from checkpoint tables.
"""

import logging
import traceback

from sqlalchemy import text

from intentkit.config.db import get_session
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


async def clear_thread_memory(agent_id: str, chat_id: str) -> bool:
    """Clear all memory content for a specific thread.

    This function directly deletes all stored checkpoints and conversation history
    associated with the specified thread from the database tables:
    - checkpoints
    - checkpoint_writes
    - checkpoint_blobs

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
        thread_id = f"{agent_id}-{chat_id}"

        # Delete directly from the checkpoint tables
        # This is necessary because AsyncShallowPostgresSaver doesn't implement adelete_thread
        async with get_session() as db:
            deletion_param = {"thread_id": thread_id}
            await db.execute(
                text("DELETE FROM checkpoints WHERE thread_id = :thread_id"),
                deletion_param,
            )
            await db.execute(
                text("DELETE FROM checkpoint_writes WHERE thread_id = :thread_id"),
                deletion_param,
            )
            await db.execute(
                text("DELETE FROM checkpoint_blobs WHERE thread_id = :thread_id"),
                deletion_param,
            )
            await db.commit()

        logger.info(f"Successfully cleared thread memory for thread_id: {thread_id}")
        return True

    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(
            f"Failed to clear thread memory for agent_id: {agent_id}, chat_id: {chat_id}. Error: {str(e)}\n{error_traceback}"
        )
        raise IntentKitAPIError(
            status_code=500, key="ServerError", message="Failed to clear thread memory"
        )
