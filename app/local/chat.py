"""IntentKit Local Chat API Router.

This module provides chat endpoints for local single-user development.
All user_id values are hardcoded to "system" for local mode.
"""

import logging
import textwrap

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
from pydantic import BaseModel, Field
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
    ChatMessageCreate,
    ChatMessageRequest,
    ChatMessageTable,
)
from intentkit.models.db import get_db
from intentkit.utils.error import IntentKitAPIError

# init logger
logger = logging.getLogger(__name__)

chat_router = APIRouter()


@chat_router.get(
    "/agents/{aid}/chat/history",
    tags=["Chat"],
    response_model=list[ChatMessage],
    operation_id="get_chat_history",
    summary="Chat History",
)
async def get_chat_history(
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Query(..., description="Chat ID to get history for"),
    db: AsyncSession = Depends(get_db),
) -> list[ChatMessage]:
    """Get last 50 messages for a specific chat.

    **Path Parameters:**
    * `aid` - Agent ID

    **Query Parameters:**
    * `chat_id` - Chat ID to get history for

    **Returns:**
    * `list[ChatMessage]` - List of chat messages, ordered by creation time ascending

    **Raises:**
    * `404` - Agent not found
    """
    # Get agent and check if exists
    agent = await get_agent(aid)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message="Agent not found"
        )

    # Get chat messages (last 50 in DESC order)
    result = await db.scalars(
        select(ChatMessageTable)
        .where(ChatMessageTable.agent_id == aid, ChatMessageTable.chat_id == chat_id)
        .order_by(desc(ChatMessageTable.created_at))
        .limit(50)
    )
    messages = result.all()

    # Reverse messages to get chronological order
    messages = [ChatMessage.model_validate(message) for message in messages[::-1]]

    # Sanitize privacy for all messages
    messages = [message.sanitize_privacy() for message in messages]

    return messages


@chat_router.post(
    "/agents/{aid}/chat/retry",
    tags=["Chat"],
    response_model=list[ChatMessage],
    operation_id="retry_chat",
    summary="Retry Chat",
)
async def retry_chat(
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Query(..., description="Chat ID to retry last message"),
    db: AsyncSession = Depends(get_db),
) -> list[ChatMessage]:
    """Retry the last message in a chat.

    If the last message is from the agent, return it directly.
    If the last message is from a user, generate a new agent response.

    **Path Parameters:**
    * `aid` - Agent ID

    **Query Parameters:**
    * `chat_id` - Chat ID to retry

    **Returns:**
    * `list[ChatMessage]` - List of chat messages including the retried response

    **Raises:**
    * `404` - Agent not found or no messages found
    * `429` - Quota exceeded
    * `500` - Internal server error
    """
    # Get agent and check if exists
    agent = await get_agent(aid)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message="Agent not found"
        )

    # Get last message
    last = await db.scalar(
        select(ChatMessageTable)
        .where(ChatMessageTable.agent_id == aid, ChatMessageTable.chat_id == chat_id)
        .order_by(desc(ChatMessageTable.created_at))
        .limit(1)
    )

    if not last:
        raise IntentKitAPIError(
            status_code=404, key="MessagesNotFound", message="No messages found"
        )

    last_message = ChatMessage.model_validate(last)
    if (
        last_message.author_type == AuthorType.AGENT
        or last_message.author_type == AuthorType.SYSTEM
    ):
        return [last_message.sanitize_privacy()]

    if last_message.author_type == AuthorType.SKILL:
        error_message_create = await ChatMessageCreate.from_system_message(
            SystemMessageType.SKILL_INTERRUPTED,
            agent_id=aid,
            chat_id=chat_id,
            user_id="system",
            author_id=aid,
            thread_type=last_message.thread_type or AuthorType.WEB,
            reply_to=last_message.id,
        )
        error_message = await error_message_create.save()
        return [last_message.sanitize_privacy(), error_message.sanitize_privacy()]

    # If last message is from user, generate a new agent response
    # Re-create and execute the user message with hardcoded user_id
    user_message = ChatMessageCreate(
        id=str(XID()),
        agent_id=aid,
        chat_id=chat_id,
        user_id="system",
        author_id="system",
        author_type=last_message.author_type or AuthorType.WEB,
        thread_type=last_message.thread_type or AuthorType.WEB,
        message=last_message.message or "",
    )
    response_messages = await execute_agent(user_message)
    return [message.sanitize_privacy() for message in response_messages]


@chat_router.post(
    "/agents/{aid}/chat",
    tags=["Chat"],
    response_model=list[ChatMessage],
    operation_id="chat",
    summary="Chat",
    description=(
        "Create a chat message and get agent's response. "
        "When `stream: true` is set in the request body, the response will be a Server-Sent Events (SSE) stream. "
        "Each event has the type 'message' and contains a ChatMessage object as JSON data. "
        "The SSE format follows the standard: `event: message\\ndata: {ChatMessage JSON}\\n\\n`. "
        "This allows real-time streaming of agent responses as they are generated."
    ),
)
async def create_chat(
    request: ChatMessageRequest,
    aid: str = Path(..., description="Agent ID"),
) -> list[ChatMessage] | StreamingResponse:
    """Create a chat message and get agent's response.

    **Process Flow:**
    1. Validates agent quota
    2. Creates a thread-specific context
    3. Executes the agent with the query
    4. Updates quota usage
    5. Saves both input and output messages

    > **Note:** This is the local-facing endpoint for single-user mode.

    **Path Parameters:**
    * `aid` - Agent ID

    **Request Body:**
    * `request` - Chat message request object (includes optional `stream` field)

    **Returns:**
    * `list[ChatMessage]` - List of chat messages including both user input and agent response
    * OR `StreamingResponse` - SSE stream when `stream: true`

    **Raises:**
    * `404` - Agent not found
    * `429` - Quota exceeded
    * `500` - Internal server error
    """
    # Get agent and validate quota
    agent = await get_agent(aid)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message=f"Agent {aid} not found"
        )

    # Create user message - hardcode user_id to "system" for local single-user mode
    user_id = "system"
    user_message = ChatMessageCreate(
        id=str(XID()),
        agent_id=aid,
        chat_id=request.chat_id,
        user_id=user_id,
        author_id=user_id,
        author_type=AuthorType.WEB,
        thread_type=AuthorType.WEB,
        message=request.message,
        attachments=request.attachments,
    )

    # Handle streaming mode
    if request.stream:

        async def stream_gen():
            async for chunk in stream_agent(user_message):
                yield f"event: message\ndata: {chunk.model_dump_json()}\n\n"

        return StreamingResponse(
            stream_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    # Execute agent (non-streaming mode)
    response_messages = await execute_agent(user_message)

    # Create or active chat
    chat = await Chat.get(request.chat_id)
    if chat:
        await chat.add_round()
    else:
        chat = ChatCreate(
            id=request.chat_id,
            agent_id=aid,
            user_id=user_id,
            summary=textwrap.shorten(request.message, width=20, placeholder="..."),
            rounds=1,
        )
        await chat.save()

    # Sanitize privacy for all messages
    return [message.sanitize_privacy() for message in response_messages]


@chat_router.get(
    "/agents/{aid}/chats",
    response_model=list[Chat],
    summary="Chat List",
    tags=["Chat"],
    operation_id="get_agent_chats",
)
async def get_agent_chats(
    aid: str = Path(..., description="Agent ID"),
):
    """Get chat list for a specific agent.

    **Path Parameters:**
    * `aid` - Agent ID

    **Returns:**
    * `list[Chat]` - List of chats for the specified agent

    **Raises:**
    * `404` - Agent not found
    """
    # Verify agent exists
    agent = await get_agent(aid)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message="Agent not found"
        )

    # Get chats by agent and hardcoded user_id "system"
    chats = await Chat.get_by_agent_user(aid, "system")
    return chats


class ChatSummaryUpdate(BaseModel):
    """Request model for updating chat summary."""

    summary: str = Field(
        ...,
        description="New summary text for the chat",
        examples=["Asked about product features and pricing"],
        min_length=1,
    )


@chat_router.patch(
    "/agents/{aid}/chats/{chat_id}",
    response_model=Chat,
    summary="Update Chat Summary",
    tags=["Chat"],
    operation_id="update_chat_summary",
)
async def update_chat_summary(
    update_data: ChatSummaryUpdate,
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Path(..., description="Chat ID"),
):
    """Update the summary of a specific chat.

    **Path Parameters:**
    * `aid` - Agent ID
    * `chat_id` - Chat ID

    **Request Body:**
    * `update_data` - Summary update data (in request body)

    **Returns:**
    * `Chat` - Updated chat object

    **Raises:**
    * `404` - Agent or chat not found
    """
    # Verify agent exists
    agent = await get_agent(aid)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message="Agent not found"
        )

    # Get chat
    chat = await Chat.get(chat_id)
    if not chat:
        raise IntentKitAPIError(
            status_code=404, key="ChatNotFound", message="Chat not found"
        )

    # Verify chat belongs to agent
    if chat.agent_id != aid:
        raise IntentKitAPIError(
            status_code=404,
            key="ChatNotFound",
            message="Chat not found for this agent",
        )

    # Update summary
    updated_chat = await chat.update_summary(update_data.summary)
    return updated_chat


@chat_router.delete(
    "/agents/{aid}/chats/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Chat",
    tags=["Chat"],
    operation_id="delete_chat",
)
async def delete_chat(
    aid: str = Path(..., description="Agent ID"),
    chat_id: str = Path(..., description="Chat ID"),
):
    """Delete a specific chat.

    **Path Parameters:**
    * `aid` - Agent ID
    * `chat_id` - Chat ID

    **Returns:**
    * `204 No Content` - Success

    **Raises:**
    * `404` - Agent or chat not found
    """
    # Verify agent exists
    agent = await get_agent(aid)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message="Agent not found"
        )

    # Get chat
    chat = await Chat.get(chat_id)
    if not chat:
        raise IntentKitAPIError(
            status_code=404, key="ChatNotFound", message="Chat not found"
        )

    # Verify chat belongs to agent
    if chat.agent_id != aid:
        raise IntentKitAPIError(
            status_code=404,
            key="ChatNotFound",
            message="Chat not found for this agent",
        )

    # Delete chat
    await chat.delete()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@chat_router.get(
    "/agents/{aid}/skill/history",
    tags=["Chat"],
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
