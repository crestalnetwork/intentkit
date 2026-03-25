"""IntentKit Local Chat API Router.

This module provides chat endpoints for local single-user development.
All user_id values are hardcoded to "system" for local mode.

The API is split into two sections:
- Thread Management: Create, list, update, delete chat threads
- Message: Send, list, retry messages in a chat thread
"""

import asyncio
import logging
import textwrap
from typing import Annotated, ClassVar

from epyxid import XID
from fastapi import (
    APIRouter,
    Depends,
    Path,
    Query,
    Response,
    status,
)
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.db import get_db, get_session
from intentkit.core.agent import get_agent
from intentkit.core.engine import execute_agent, stream_agent
from intentkit.core.task_registry import cancel_task, register_task, unregister_task
from intentkit.models.app_setting import SystemMessageType
from intentkit.models.chat import (
    AuthorType,
    Chat,
    ChatCreate,
    ChatMessage,
    ChatMessageAttachment,
    ChatMessageCreate,
    ChatMessageTable,
)
from intentkit.models.llm import create_llm_model
from intentkit.models.llm_picker import pick_summarize_model
from intentkit.utils.error import IntentKitAPIError

# init logger
logger = logging.getLogger(__name__)

chat_router = APIRouter()

# Hardcoded user_id for local single-user mode
LOCAL_USER_ID = "system"
SUMMARY_TITLE_SYSTEM_PROMPT = (
    "Generate a concise chat title in the same language as the conversation. "
    "Return title text only, with no quotes or explanations."
)


# =============================================================================
# Response Models
# =============================================================================


class ChatMessagesResponse(BaseModel):
    """Response model for chat messages with pagination."""

    data: list[ChatMessage]
    has_more: bool = False
    next_cursor: str | None = None

    model_config: ClassVar[ConfigDict] = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {"data": [], "has_more": False, "next_cursor": None}
        },
    )


# =============================================================================
# Request Models
# =============================================================================


class ChatUpdateRequest(BaseModel):
    """Request model for updating a chat thread."""

    summary: Annotated[
        str,
        Field(
            ...,
            description="Updated summary for the chat thread",
            examples=["Updated chat summary"],
            max_length=500,
        ),
    ]

    model_config: ClassVar[ConfigDict] = ConfigDict(
        json_schema_extra={"example": {"summary": "Updated chat summary"}},
    )


class LocalChatCreateRequest(BaseModel):
    """Request model for creating a local chat thread."""

    chat_id: Annotated[
        str | None,
        Field(
            None,
            description="Optional client-provided chat id (reserved, currently ignored)",
        ),
    ] = None
    first_message: Annotated[
        str | None,
        Field(
            None,
            description="Optional first user message used to generate chat title",
            max_length=65535,
        ),
    ] = None


class LocalChatMessageRequest(BaseModel):
    """Request model for local chat messages.

    This model represents the request body for creating a new chat message.
    Simplified for local single-user mode without user_id and app_id.
    """

    message: Annotated[
        str,
        Field(
            ...,
            description="Content of the message",
            examples=["Hello, how can you help me today?"],
            min_length=1,
            max_length=65535,
        ),
    ]
    stream: Annotated[
        bool | None,
        Field(
            None,
            description="Whether to stream the response",
        ),
    ]
    attachments: Annotated[
        list[ChatMessageAttachment] | None,
        Field(
            None,
            description="Optional list of attachments (links, images, or files)",
            examples=[[{"type": "link", "url": "https://example.com"}]],
        ),
    ]

    model_config: ClassVar[ConfigDict] = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "message": "Hello, how can you help me today?",
                "attachments": [
                    {
                        "type": "link",
                        "url": "https://example.com",
                    }
                ],
            }
        },
    )


def _is_user_author_type(author_type: AuthorType) -> bool:
    return author_type == AuthorType.WEB


async def _count_user_messages(agent_id: str, chat_id: str) -> int:
    async with get_session() as db:
        count = await db.scalar(
            select(func.count())
            .select_from(ChatMessageTable)
            .where(
                ChatMessageTable.agent_id == agent_id,
                ChatMessageTable.chat_id == chat_id,
                ChatMessageTable.author_type == AuthorType.WEB,
            )
        )
        return int(count or 0)


async def should_schedule_chat_summary(
    agent_id: str, chat_id: str, incoming_author_type: AuthorType
) -> bool:
    if not _is_user_author_type(incoming_author_type):
        return False
    previous_user_count = await _count_user_messages(agent_id, chat_id)
    return previous_user_count + 1 == 3


def _extract_model_response_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
                    continue
            text = getattr(item, "text", None)
            if isinstance(text, str):
                parts.append(text)
        return "".join(parts)
    return str(content)


def _normalize_summary_title(title: str) -> str:
    normalized = " ".join(title.split())
    return normalized[:40]


async def _generate_summary_title(prompt_text: str) -> str:
    content = prompt_text.strip()
    if not content:
        return ""

    summarize_model = pick_summarize_model()
    llm = await create_llm_model(model_name=summarize_model, temperature=0.2)
    model = await llm.create_instance()
    response = await model.ainvoke(
        [
            SystemMessage(content=SUMMARY_TITLE_SYSTEM_PROMPT),
            HumanMessage(content=content),
        ]
    )
    raw_title = _extract_model_response_text(response.content)
    return _normalize_summary_title(raw_title)


async def _load_first_three_round_transcript(agent_id: str, chat_id: str) -> str:
    async with get_session() as db:
        rows = await db.scalars(
            select(ChatMessageTable)
            .where(
                ChatMessageTable.agent_id == agent_id,
                ChatMessageTable.chat_id == chat_id,
            )
            .order_by(ChatMessageTable.created_at)
            .limit(200)
        )
        messages = [ChatMessage.model_validate(row) for row in rows.all()]

    user_round_count = 0
    transcript_lines: list[str] = []
    for message in messages:
        if _is_user_author_type(message.author_type):
            user_round_count += 1
            if user_round_count > 3:
                break

        content = message.message.strip()
        if not content:
            continue

        if _is_user_author_type(message.author_type):
            role = "User"
        elif message.author_type == AuthorType.AGENT:
            role = "Assistant"
        elif message.author_type == AuthorType.SKILL:
            role = "Tool"
        else:
            role = "System"
        transcript_lines.append(f"{role}: {content}")

    return "\n".join(transcript_lines)


async def _generate_chat_summary_title(agent_id: str, chat_id: str) -> str:
    transcript = await _load_first_three_round_transcript(agent_id, chat_id)
    if not transcript:
        return ""

    return await _generate_summary_title(f"Conversation:\n{transcript}")


async def _update_chat_summary_title(agent_id: str, chat_id: str) -> None:
    chat = await Chat.get(chat_id)
    if not chat:
        logger.info(
            f"Skip chat summary title update because chat was not found: {chat_id}"
        )
        return
    if chat.agent_id != agent_id:
        return

    try:
        title = await _generate_chat_summary_title(agent_id, chat_id)
        if not title:
            return
        _ = await chat.update_summary(title)
    except Exception:
        logger.exception(
            f"Failed to generate chat summary title for chat {chat_id} of agent {agent_id}"
        )


def schedule_chat_summary_title_update(agent_id: str, chat_id: str) -> None:
    _ = asyncio.create_task(_update_chat_summary_title(agent_id, chat_id))


def should_summarize_first_message(first_message: str | None) -> bool:
    if not first_message:
        return False
    return len(first_message.encode("utf-8")) > 20


async def update_chat_summary_from_first_message(
    agent_id: str, chat_id: str, first_message: str
) -> None:
    chat = await Chat.get(chat_id)
    if not chat:
        logger.info(
            f"Skip chat summary title update because chat was not found: {chat_id}"
        )
        return
    if chat.agent_id != agent_id:
        return

    try:
        title = await _generate_summary_title(f"First user message:\n{first_message}")
        if not title:
            return
        _ = await chat.update_summary(title)
    except Exception:
        logger.exception(
            f"Failed to generate first-message summary title for chat {chat_id} of agent {agent_id}"
        )


# =============================================================================
# Thread Management Endpoints
# =============================================================================


@chat_router.get(
    "/agents/{aid}/chats",
    response_model=list[Chat],
    operation_id="list_chats",
    summary="List chat threads",
    description="Retrieve all chat threads for the agent.",
    tags=["Thread"],
)
async def list_chats(
    aid: str = Path(..., description="Agent ID"),
):
    """Get a list of chat threads for an agent."""
    agent = await get_agent(aid)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message=f"Agent {aid} not found"
        )

    return await Chat.get_by_agent_user(aid, LOCAL_USER_ID)


@chat_router.post(
    "/agents/{aid}/chats",
    response_model=Chat,
    operation_id="create_chat_thread",
    summary="Create a new chat thread",
    description="Create a new chat thread for the agent.",
    tags=["Thread"],
)
async def create_chat_thread(
    request: LocalChatCreateRequest | None = None,
    aid: str = Path(..., description="Agent ID"),
):
    """Create a new chat thread."""
    agent = await get_agent(aid)
    if not agent:
        raise IntentKitAPIError(
            status_code=404,
            key="AgentNotFound",
            message=f"Agent {aid} not found",
        )

    chat = ChatCreate(
        id=str(XID()),
        agent_id=aid,
        user_id=LOCAL_USER_ID,
        summary="",
        rounds=0,
    )
    _ = await chat.save()
    if request and should_summarize_first_message(request.first_message):
        await update_chat_summary_from_first_message(
            aid, chat.id, request.first_message or ""
        )
    # Retrieve the full Chat object with auto-generated fields
    full_chat = await Chat.get(chat.id)
    return full_chat


@chat_router.patch(
    "/agents/{aid}/chats/{chat_id}",
    response_model=Chat,
    operation_id="update_chat_thread",
    summary="Update a chat thread",
    description="Update details of a specific chat thread. Currently only supports updating the summary.",
    tags=["Thread"],
)
async def update_chat_thread(
    request: ChatUpdateRequest,
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Path(..., description="Chat ID"),
):
    """Update a chat thread."""
    agent = await get_agent(aid)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message=f"Agent {aid} not found"
        )

    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != aid:
        raise IntentKitAPIError(
            status_code=404, key="ChatNotFound", message="Chat not found"
        )

    # Update the summary field
    updated_chat = await chat.update_summary(request.summary)
    return updated_chat


@chat_router.delete(
    "/agents/{aid}/chats/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_chat_thread",
    summary="Delete a chat thread",
    description="Delete a specific chat thread.",
    tags=["Thread"],
)
async def delete_chat_thread(
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Path(..., description="Chat ID"),
):
    """Delete a chat thread."""
    agent = await get_agent(aid)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message=f"Agent {aid} not found"
        )

    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != aid:
        raise IntentKitAPIError(
            status_code=404, key="ChatNotFound", message="Chat not found"
        )

    await chat.delete()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# =============================================================================
# Message Endpoints
# =============================================================================


@chat_router.get(
    "/agents/{aid}/chats/{chat_id}/messages",
    response_model=ChatMessagesResponse,
    operation_id="list_messages_in_chat",
    summary="List messages in a chat thread",
    description="Retrieve the message history for a specific chat thread with cursor-based pagination.",
    tags=["Message"],
)
async def list_messages(
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Path(..., description="Chat ID"),
    db: AsyncSession = Depends(get_db),
    cursor: str | None = Query(None, description="Cursor for pagination (message id)"),
    limit: int = Query(
        20, ge=1, le=100, description="Maximum number of messages to return"
    ),
) -> ChatMessagesResponse:
    """Get the message history for a chat thread with cursor-based pagination."""
    agent = await get_agent(aid)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message=f"Agent {aid} not found"
        )

    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != aid:
        raise IntentKitAPIError(
            status_code=404, key="ChatNotFound", message="Chat not found"
        )

    stmt = (
        select(ChatMessageTable)
        .where(ChatMessageTable.agent_id == aid, ChatMessageTable.chat_id == chat_id)
        .order_by(desc(ChatMessageTable.id))
        .limit(limit + 1)
    )
    if cursor:
        stmt = stmt.where(ChatMessageTable.id < cursor)
    result = await db.scalars(stmt)
    messages = result.all()
    has_more = len(messages) > limit
    messages_to_return = messages[:limit]
    next_cursor = (
        str(messages_to_return[-1].id) if has_more and messages_to_return else None
    )
    # Return as ChatMessagesResponse object
    return ChatMessagesResponse(
        data=[ChatMessage.model_validate(m) for m in messages_to_return],
        has_more=has_more,
        next_cursor=next_cursor,
    )


@chat_router.post(
    "/agents/{aid}/chats/{chat_id}/messages",
    response_model=list[ChatMessage],
    operation_id="send_message_to_chat",
    summary="Send a message to a chat thread",
    description=(
        "Send a new message to a specific chat thread. The response is a list of messages generated by the agent. "
        "The response does not include the original user message. It could be skill calls, agent messages, or system error messages.\n\n"
        "**Stream Mode:**\n"
        "When `stream: true` is set in the request body, the response will be a Server-Sent Events (SSE) stream. "
        "Each event has the type 'message' and contains a ChatMessage object as JSON data. "
        "The SSE format follows the standard: `event: message\\ndata: {ChatMessage JSON}\\n\\n`. "
        "This allows real-time streaming of agent responses as they are generated, including intermediate skill calls and final responses."
    ),
    tags=["Message"],
)
async def send_message(
    request: LocalChatMessageRequest,
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Path(..., description="Chat ID"),
):
    """Send a new message to a chat thread."""
    agent = await get_agent(aid)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message=f"Agent {aid} not found"
        )

    # Verify that the chat exists
    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != aid:
        raise IntentKitAPIError(
            status_code=404, key="ChatNotFound", message="Chat not found"
        )

    should_schedule_summary = await should_schedule_chat_summary(
        aid, chat_id, AuthorType.WEB
    )

    # Update summary if it's empty
    if not chat.summary:
        summary = textwrap.shorten(request.message, width=20, placeholder="...")
        _ = await chat.update_summary(summary)

    # Increment the round count
    await chat.add_round()

    user_message = ChatMessageCreate(
        id=str(XID()),
        agent_id=aid,
        chat_id=chat_id,
        user_id=LOCAL_USER_ID,
        author_id=LOCAL_USER_ID,
        author_type=AuthorType.WEB,
        thread_type=AuthorType.WEB,
        message=request.message,
        attachments=request.attachments,
        model=None,
        reply_to=None,
        skill_calls=None,
        input_tokens=0,
        output_tokens=0,
        time_cost=0.0,
        credit_event_id=None,
        credit_cost=None,
        cold_start_cost=0.0,
    )

    if request.stream:

        async def stream_gen():
            current_task = asyncio.current_task()
            if current_task:
                register_task(aid, chat_id, current_task)
            try:
                async for chunk in stream_agent(user_message):
                    yield f"event: message\ndata: {chunk.model_dump_json()}\n\n"
                if should_schedule_summary:
                    schedule_chat_summary_title_update(aid, chat_id)
            except asyncio.CancelledError:
                logger.info("Stream cancelled for agent %s, chat %s", aid, chat_id)
                return
            finally:
                unregister_task(aid, chat_id)

        return StreamingResponse(
            stream_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    else:
        response_messages = await execute_agent(user_message)
        if should_schedule_summary:
            schedule_chat_summary_title_update(aid, chat_id)
        # Return messages list directly for compatibility with stream mode
        return response_messages


@chat_router.post(
    "/agents/{aid}/chats/{chat_id}/cancel",
    operation_id="cancel_generation",
    summary="Cancel an in-progress generation",
    description="Cancel an in-progress streaming response for a specific chat thread.",
    tags=["Message"],
)
async def cancel_generation(
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Path(..., description="Chat ID"),
):
    """Cancel an in-progress generation."""
    cancelled = cancel_task(aid, chat_id)
    return {"cancelled": cancelled}


@chat_router.post(
    "/agents/{aid}/chats/{chat_id}/messages/retry",
    response_model=list[ChatMessage],
    operation_id="retry_message_in_chat",
    summary="Retry a message in a chat thread",
    description="Retry sending the last message in a specific chat thread. If the last message is from the system, returns all messages after the last user message. If the last message is from a user, generates a new response. Only works with non-streaming mode.",
    tags=["Message"],
)
async def retry_message(
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Path(..., description="Chat ID"),
    db: AsyncSession = Depends(get_db),
):
    """Retry the last message in a chat thread.

    If the last message is from the system, return all messages after the last user message.
    If the last message is from a user, generate a new response.
    Note: Retry only works in non-streaming mode.
    """
    agent = await get_agent(aid)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message=f"Agent {aid} not found"
        )

    # Verify that the chat exists
    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != aid:
        raise IntentKitAPIError(
            status_code=404, key="ChatNotFound", message="Chat not found"
        )

    last = await db.scalar(
        select(ChatMessageTable)
        .where(ChatMessageTable.agent_id == aid, ChatMessageTable.chat_id == chat_id)
        .order_by(desc(ChatMessageTable.created_at))
        .limit(1)
    )

    if not last:
        raise IntentKitAPIError(
            status_code=404, key="NoMessagesFound", message="No messages found"
        )

    last_message = ChatMessage.model_validate(last)

    # If last message is from system, find all messages after last user message
    if (
        last_message.author_type == AuthorType.AGENT
        or last_message.author_type == AuthorType.SYSTEM
    ):
        # Find the last user message
        last_user_message = await db.scalar(
            select(ChatMessageTable)
            .where(
                ChatMessageTable.agent_id == aid,
                ChatMessageTable.chat_id == chat_id,
                ChatMessageTable.author_type == AuthorType.WEB,
            )
            .order_by(desc(ChatMessageTable.created_at))
            .limit(1)
        )

        if not last_user_message:
            # If no user message found, just return the last message
            return [last_message]

        # Get all messages after the last user message
        messages_after_user = await db.scalars(
            select(ChatMessageTable)
            .where(
                ChatMessageTable.agent_id == aid,
                ChatMessageTable.chat_id == chat_id,
                ChatMessageTable.created_at > last_user_message.created_at,
            )
            .order_by(ChatMessageTable.created_at)
        )

        messages_list = messages_after_user.all()
        if messages_list:
            return [ChatMessage.model_validate(msg) for msg in messages_list]
        else:
            # Fallback to just the last message if no messages found after user message
            return [last_message]

    # If last message is from skill, provide warning message
    if last_message.author_type == AuthorType.SKILL:
        error_message_create = await ChatMessageCreate.from_system_message(
            SystemMessageType.SKILL_INTERRUPTED,
            agent_id=aid,
            chat_id=chat_id,
            user_id=LOCAL_USER_ID,
            author_id=aid,
            thread_type=last_message.thread_type or AuthorType.WEB,
            reply_to=last_message.id,
            time_cost=0.0,
        )
        error_message = await error_message_create.save()
        return [last_message, error_message]

    # If last message is from user, generate a new response
    # Create a new user message for retry (non-streaming only)
    retry_user_message = ChatMessageCreate(
        id=str(XID()),
        agent_id=aid,
        chat_id=chat_id,
        user_id=LOCAL_USER_ID,
        author_id=LOCAL_USER_ID,
        author_type=AuthorType.WEB,
        thread_type=AuthorType.WEB,
        message=last_message.message or "",
        attachments=last_message.attachments,
        model=None,
        reply_to=None,
        skill_calls=None,
        input_tokens=0,
        output_tokens=0,
        time_cost=0.0,
        credit_event_id=None,
        credit_cost=None,
        cold_start_cost=0.0,
    )

    # Execute handler (non-streaming mode only)
    response_messages = await execute_agent(retry_user_message)

    # Return messages list directly for compatibility with send_message
    return response_messages


# =============================================================================
# Utility Endpoints
# =============================================================================


@chat_router.get(
    "/agents/{aid}/skill/history",
    tags=["Utility"],
    response_model=list[ChatMessage],
    operation_id="get_skill_history",
    summary="Skill History",
)
async def get_skill_history(
    aid: str = Path(..., description="Agent ID"),
    db: AsyncSession = Depends(get_db),
) -> list[ChatMessage]:
    """Get last 50 skill messages for a specific agent.

    **Path Parameters:**
    * `aid` - Agent ID

    **Returns:**
    * `list[ChatMessage]` - List of skill messages, ordered by creation time ascending

    **Raises:**
    * `404` - Agent not found
    """
    # Get agent and check if exists
    agent = await get_agent(aid)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message="Agent not found"
        )

    # Get skill messages (last 50 in DESC order)
    result = await db.scalars(
        select(ChatMessageTable)
        .where(
            ChatMessageTable.agent_id == aid,
            ChatMessageTable.author_type == AuthorType.SKILL,
        )
        .order_by(desc(ChatMessageTable.created_at))
        .limit(50)
    )
    messages = result.all()

    # Reverse messages to get chronological order
    messages = [ChatMessage.model_validate(message) for message in messages[::-1]]

    # Sanitize privacy for all messages

    return messages
