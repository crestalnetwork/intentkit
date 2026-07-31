"""Checkpoint recovery and cleanup for the chat engine.

Handles dangling state after cancellations, empty model outputs (e.g. Gemini
MALFORMED_FUNCTION_CALL) and unrecoverable checkpoint corruption.
"""

import logging
import time
from typing import Any

from epyxid import XID
from langchain_core.messages import AIMessage, RemoveMessage
from langchain_core.runnables import RunnableConfig
from langgraph.errors import InvalidUpdateError

from intentkit.core.engine.content import (
    extract_text_content,
    extract_thinking_content,
)
from intentkit.models.chat import AuthorType, ChatMessageCreate

logger = logging.getLogger(__name__)


def is_unrecoverable_checkpoint_error(exc: Exception) -> bool:
    """Check if an exception indicates unrecoverable checkpoint corruption.

    Only these cases warrant clearing thread memory. Transient errors
    (LLM API failures, network issues, etc.) should preserve conversation history.
    """
    import json
    import pickle
    import struct

    # Checkpoint state machine corruption
    if isinstance(exc, InvalidUpdateError):
        return True

    # Deserialization failure in checkpoint data (pickle, JSON, msgpack paths)
    unrecoverable_types: tuple[type[Exception], ...] = (
        pickle.UnpicklingError,
        struct.error,
        json.JSONDecodeError,
    )
    try:
        import ormsgpack

        unrecoverable_types = (*unrecoverable_types, ormsgpack.MsgpackDecodeError)
    except ImportError:
        pass

    return isinstance(exc, unrecoverable_types)


def summarize_history_messages(msgs: list[Any], max_messages: int = 10) -> list[dict]:
    """Build a compact summary of the last N thread messages.

    Focuses on tool_calls carried on AIMessage — useful when the LLM returns
    MALFORMED_FUNCTION_CALL and the offending call isn't present in the current
    turn's chunks, so we have to look back in checkpoint history.
    """
    summary: list[dict] = []
    for msg in msgs[-max_messages:]:
        entry: dict = {
            "type": type(msg).__name__,
            "id": getattr(msg, "id", None),
        }
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            entry["tool_calls"] = [
                {"name": tc.get("name"), "args": tc.get("args")} for tc in tool_calls
            ]
        invalid_tc = getattr(msg, "invalid_tool_calls", None)
        if invalid_tc:
            entry["invalid_tool_calls"] = invalid_tc
        content = getattr(msg, "content", None)
        if content:
            preview = extract_text_content(content) or str(content)
            entry["content_preview"] = preview[:200]
        thinking = extract_thinking_content(msg)
        if thinking:
            entry["thinking_preview"] = thinking[:200]
        response_meta = getattr(msg, "response_metadata", None)
        if response_meta and "finish_reason" in response_meta:
            entry["finish_reason"] = response_meta["finish_reason"]
        summary.append(entry)
    return summary


async def cleanup_empty_model_output(
    executor: Any,
    stream_config: RunnableConfig,
    agent_id: str,
    thread_id: str,
) -> list[Any]:
    """Handle checkpoint fallout from a zero-output model turn (e.g. Gemini
    MALFORMED_FUNCTION_CALL).

    Returns the full message list (for diagnostics) and, if the last message
    is an empty AIMessage (no content, no tool_calls), removes it so the next
    user turn doesn't inherit the junk state. Without this the thread keeps
    the empty message and subsequent turns may misbehave.
    """
    try:
        snap = await executor.aget_state(stream_config)
        msgs = snap.values.get("messages") if snap.values else None
    except Exception:
        logger.warning(
            f"Failed to fetch thread state for {agent_id}",
            extra={"thread_id": thread_id},
            exc_info=True,
        )
        return []

    if not msgs:
        return []

    last = msgs[-1]
    # Treat list-content (e.g. thinking-only blocks) as empty when
    # extract_text_content yields nothing — a non-empty list is still truthy
    # so a direct `not last.content` check would miss these.
    if (
        isinstance(last, AIMessage)
        and not extract_text_content(last.content)
        and not last.tool_calls
    ):
        if not last.id:
            logger.warning(
                f"Empty AIMessage has no id; skipping removal for {agent_id}",
                extra={"thread_id": thread_id},
            )
        else:
            try:
                await executor.aupdate_state(
                    stream_config,
                    {"messages": [RemoveMessage(id=last.id)]},
                )
                logger.info(
                    f"Removed empty AIMessage for {agent_id}",
                    extra={"thread_id": thread_id},
                )
            except Exception:
                logger.warning(
                    f"Failed to remove empty AIMessage for {agent_id}",
                    extra={"thread_id": thread_id},
                    exc_info=True,
                )
    return msgs


async def cancel_cleanup(
    executor: Any,
    stream_config: RunnableConfig,
    in_tools_phase: bool,
    user_message: ChatMessageCreate,
    thread_id: str,
    start: float,
) -> None:
    """Run cancel-time DB cleanup, intended to be called inside asyncio.shield()."""
    if in_tools_phase:
        # Cancelled during tool execution — checkpoint has tool_calls without results.
        # Remove the last AIMessage (with tool_calls) to prevent re-execution on next message.
        try:
            snap = await executor.aget_state(stream_config)
            msgs = snap.values.get("messages") if snap.values else None
            if msgs and isinstance(msgs[-1], AIMessage) and msgs[-1].tool_calls:
                await executor.aupdate_state(
                    stream_config,
                    {"messages": [RemoveMessage(id=msgs[-1].id)]},
                )
                logger.info(
                    f"Removed dangling tool_call message for {user_message.agent_id}",
                    extra={"thread_id": thread_id},
                )
            else:
                logger.info(
                    f"No dangling tool_call found for {user_message.agent_id}, skipping cleanup",
                    extra={"thread_id": thread_id},
                )
        except Exception:
            logger.warning(
                f"Failed to remove dangling tool_call message, clearing thread for {user_message.agent_id}",
                extra={"thread_id": thread_id},
                exc_info=True,
            )
    # Save cancellation message directly (stream is already dead, can't yield)
    cancel_message_create = ChatMessageCreate(
        id=str(XID()),
        agent_id=user_message.agent_id,
        chat_id=user_message.chat_id,
        user_id=user_message.user_id,
        author_id=user_message.agent_id,
        author_type=AuthorType.SYSTEM,
        thread_type=user_message.thread_entrypoint,
        reply_to=user_message.id,
        message="User cancelled the conversation",
        time_cost=time.perf_counter() - start,
    )
    await cancel_message_create.save()
