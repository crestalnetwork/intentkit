"""Chat memory management utilities.

This module provides functions for managing chat thread memory,
including clearing thread history by directly deleting from checkpoint tables,
and appending proactive messages to both chat_messages and LangGraph checkpoints.
"""

import logging
import traceback

from epyxid import XID
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from sqlalchemy import text

from intentkit.config.db import get_session
from intentkit.models.chat import AuthorType, ChatMessage, ChatMessageCreate
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

        logger.info("Successfully cleared thread memory for thread_id: %s", thread_id)
        return True

    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(
            f"Failed to clear thread memory for agent_id: {agent_id}, chat_id: {chat_id}. Error: {str(e)}\n{error_traceback}"
        )
        raise IntentKitAPIError(
            status_code=500, key="ServerError", message="Failed to clear thread memory"
        )


async def append_agent_message(
    agent_id: str,
    chat_id: str,
    text: str,
    thread_type: AuthorType = AuthorType.INTERNAL,
) -> ChatMessage:
    """Append an agent message to both chat_messages and LangGraph checkpoint.

    This is for proactive (push) messages that originate from the system,
    not from a streaming LLM execution.

    Args:
        agent_id: The agent ID (e.g. "team-xxx" for lead agents)
        chat_id: The chat ID (e.g. "tg_team:xxx:123")
        text: The message text
        thread_type: The thread type for the message

    Returns:
        The saved ChatMessage
    """
    msg_id = str(XID())

    msg_create = ChatMessageCreate(
        id=msg_id,
        agent_id=agent_id,
        chat_id=chat_id,
        user_id=agent_id,
        author_id=agent_id,
        author_type=AuthorType.AGENT,
        thread_type=thread_type,
        message=text,
    )
    saved_msg = await msg_create.save()

    # Try to append to LangGraph checkpoint (best-effort)
    try:
        executor = _get_cached_executor(agent_id)
        if executor:
            thread_id = f"{agent_id}-{chat_id}"
            config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
            ai_msg = AIMessage(content=text, id=msg_id)
            await executor.aupdate_state(config, {"messages": [ai_msg]})
            logger.info("Appended push message to checkpoint: %s", thread_id)
        else:
            logger.debug(
                "No cached executor for %s, skipping checkpoint update", agent_id
            )
    except Exception:
        logger.warning(
            "Failed to append message to checkpoint for %s-%s",
            agent_id,
            chat_id,
            exc_info=True,
        )

    return saved_msg


def _get_cached_executor(agent_id: str):
    """Get a cached executor for the agent, or None if not cached.

    Checks both lead executor cache and regular agent executor cache.
    Does NOT build a new executor — returns None if not found.
    """
    # Check lead executor cache.
    # Lead inbound messages use raw team_id as agent_id, so check directly.
    try:
        from intentkit.core.lead.cache import lead_executors

        executor = lead_executors.get(agent_id)
        if executor:
            return executor
    except ImportError:
        pass

    # Check regular agent executor cache
    try:
        from intentkit.core.executor import agents

        executor = agents.get(agent_id)
        if executor:
            return executor
    except ImportError:
        pass

    return None
