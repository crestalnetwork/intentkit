"""IntentKit Local Chat API Router.

This module provides chat endpoints for local single-user development.
All user_id values are hardcoded to "system" for local mode.

The API is split into two sections:
- Thread Management: Create, list, update, delete chat threads
- Message: Send, list, retry messages in a chat thread
"""

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
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.core.agent import get_agent
from intentkit.core.engine import execute_agent, stream_agent
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
from intentkit.models.db import get_db
from intentkit.utils.error import IntentKitAPIError

# init logger
logger = logging.getLogger(__name__)

chat_router = APIRouter()

# Hardcoded user_id for local single-user mode
LOCAL_USER_ID = "system"


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
    search_mode: Annotated[
        bool | None,
        Field(
            None,
            description="Optional flag to enable search mode",
        ),
    ]
    super_mode: Annotated[
        bool | None,
        Field(
            None,
            description="Optional flag to enable super mode",
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
                "search_mode": True,
                "super_mode": False,
                "attachments": [
                    {
                        "type": "link",
                        "url": "https://example.com",
                    }
                ],
            }
        },
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
        data=[
            ChatMessage.model_validate(m).sanitize_privacy() for m in messages_to_return
        ],
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
        search_mode=request.search_mode,
        super_mode=request.super_mode,
    )

    if request.stream:

        async def stream_gen():
            async for chunk in stream_agent(user_message):
                yield f"event: message\ndata: {chunk.model_dump_json()}\n\n"

        return StreamingResponse(
            stream_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    else:
        response_messages = await execute_agent(user_message)
        # Return messages list directly for compatibility with stream mode
        return [message.sanitize_privacy() for message in response_messages]


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
            return [last_message.sanitize_privacy()]

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
            return [
                ChatMessage.model_validate(msg).sanitize_privacy()
                for msg in messages_list
            ]
        else:
            # Fallback to just the last message if no messages found after user message
            return [last_message.sanitize_privacy()]

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
        return [last_message.sanitize_privacy(), error_message.sanitize_privacy()]

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
        search_mode=last_message.search_mode,
        super_mode=last_message.super_mode,
    )

    # Execute handler (non-streaming mode only)
    response_messages = await execute_agent(retry_user_message)

    # Return messages list directly for compatibility with send_message
    return [message.sanitize_privacy() for message in response_messages]


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
    messages = [message.sanitize_privacy() for message in messages]

    return messages
