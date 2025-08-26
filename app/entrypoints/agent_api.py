"""IntentKit Chat API Router."""

import logging
import textwrap
from typing import Annotated, List, Optional

from epyxid import XID
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AgentToken, verify_agent_token
from intentkit.core.engine import execute_agent, stream_agent
from intentkit.models.agent import Agent, AgentResponse
from intentkit.models.agent_data import AgentData
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

logger = logging.getLogger(__name__)

router_rw = APIRouter()
router_ro = APIRouter()


def get_real_user_id(
    agent_token: AgentToken, user_id: Optional[str], agent_owner: Optional[str]
) -> str:
    """Generate real user_id based on agent token and user_id.

    Args:
        agent_token: Agent token containing agent_id and is_public flag
        user_id: Optional user ID
        agent_owner: Agent owner ID

    Returns:
        Real user ID string

    Raises:
        HTTPException: If user_id is provided for a private agent
    """
    if user_id:
        return f"{agent_token.agent_id}_{user_id}"
    else:
        if agent_token.is_public:
            return f"{agent_token.agent_id}_anonymous"
        else:
            return agent_owner or agent_token.agent_id


class ChatMessagesResponse(BaseModel):
    """Response model for chat messages with pagination."""

    data: List[ChatMessage]
    has_more: bool = False
    next_cursor: Optional[str] = None

    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {"data": [], "has_more": False, "next_cursor": None}
        },
    )


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

    model_config = ConfigDict(
        json_schema_extra={"example": {"summary": "Updated chat summary"}},
    )


class ChatMessageRequest(BaseModel):
    """Request model for chat messages.

    This model represents the request body for creating a new chat message.
    It contains the necessary fields to identify the chat context and message
    content, along with optional attachments. The user ID is optional and
    combined with internal ID for storage if provided.
    """

    user_id: Annotated[
        Optional[str],
        Field(
            None,
            description="User ID (optional). When provided (whether API key uses pk or sk), only public skills will be accessible.",
            examples=["user-123"],
        ),
    ]
    app_id: Annotated[
        Optional[str],
        Field(
            None,
            description="Optional application identifier",
            examples=["app-789"],
        ),
    ]
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
        Optional[bool],
        Field(
            None,
            description="Whether to stream the response",
        ),
    ]
    search_mode: Annotated[
        Optional[bool],
        Field(
            None,
            description="Optional flag to enable search mode",
        ),
    ]
    super_mode: Annotated[
        Optional[bool],
        Field(
            None,
            description="Optional flag to enable super mode",
        ),
    ]
    attachments: Annotated[
        Optional[List[ChatMessageAttachment]],
        Field(
            None,
            description="Optional list of attachments (links, images, or files)",
            examples=[[{"type": "link", "url": "https://example.com"}]],
        ),
    ]

    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "user_id": "user-123",
                "app_id": "app-789",
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


@router_ro.get(
    "/chats",
    response_model=List[Chat],
    operation_id="list_chats",
    summary="List chat threads",
    description="Retrieve all chat threads for the current user.",
    tags=["Thread"],
)
async def get_chats(
    user_id: Optional[str] = Query(
        None,
        description="User ID (optional). When provided (whether API key uses pk or sk), only public skills will be accessible.",
    ),
    agent_token: AgentToken = Depends(verify_agent_token),
):
    """Get a list of chat threads."""
    agent_id = agent_token.agent_id
    # Get agent to access owner
    agent = await Agent.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Entity {agent_id} not found")

    real_user_id = get_real_user_id(agent_token, user_id, agent.owner)
    return await Chat.get_by_agent_user(agent_id, real_user_id)


@router_rw.post(
    "/chats",
    response_model=Chat,
    operation_id="create_chat_thread",
    summary="Create a new chat thread",
    description="Create a new chat thread for a specific user.",
    tags=["Thread"],
)
async def create_chat(
    user_id: Optional[str] = Query(
        None,
        description="User ID (optional). When provided (whether API key uses pk or sk), only public skills will be accessible.",
    ),
    agent_token: AgentToken = Depends(verify_agent_token),
):
    """Create a new chat thread."""
    agent_id = agent_token.agent_id
    # Verify that the entity exists
    agent = await Agent.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Entity {agent_id} not found")

    real_user_id = get_real_user_id(agent_token, user_id, agent.owner)
    chat = ChatCreate(
        id=str(XID()),
        agent_id=agent_id,
        user_id=real_user_id,
        summary="",
        rounds=0,
    )
    await chat.save()
    # Retrieve the full Chat object with auto-generated fields
    full_chat = await Chat.get(chat.id)
    return full_chat


@router_ro.get(
    "/chats/{chat_id}",
    response_model=Chat,
    operation_id="get_chat_thread_by_id",
    summary="Get chat thread by ID",
    description="Retrieve a specific chat thread by its ID for the current user. Returns 404 if not found or not owned by the user.",
    tags=["Thread"],
)
async def get_chat(
    chat_id: str = Path(..., description="Chat ID"),
    user_id: Optional[str] = Query(
        None,
        description="User ID (optional). When provided (whether API key uses pk or sk), only public skills will be accessible.",
    ),
    agent_token: AgentToken = Depends(verify_agent_token),
):
    """Get a specific chat thread."""
    agent_id = agent_token.agent_id
    # Get agent to access owner
    agent = await Agent.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Entity {agent_id} not found")

    real_user_id = get_real_user_id(agent_token, user_id, agent.owner)
    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != agent_id or chat.user_id != real_user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
        )
    return chat


@router_rw.patch(
    "/chats/{chat_id}",
    response_model=Chat,
    operation_id="update_chat_thread",
    summary="Update a chat thread",
    description="Update details of a specific chat thread. Currently only supports updating the summary.",
    tags=["Thread"],
)
async def update_chat(
    request: ChatUpdateRequest,
    chat_id: str = Path(..., description="Chat ID"),
    agent_token: AgentToken = Depends(verify_agent_token),
):
    """Update a chat thread."""
    agent_id = agent_token.agent_id
    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
        )

    # Update the summary field
    updated_chat = await chat.update_summary(request.summary)

    return updated_chat


@router_rw.delete(
    "/chats/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_chat_thread",
    summary="Delete a chat thread",
    description="Delete a specific chat thread for the current user. Returns 404 if not found or not owned by the user.",
    tags=["Thread"],
)
async def delete_chat(
    chat_id: str = Path(..., description="Chat ID"),
    agent_token: AgentToken = Depends(verify_agent_token),
):
    """Delete a chat thread."""
    agent_id = agent_token.agent_id
    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
        )
    await chat.delete()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router_ro.get(
    "/chats/{chat_id}/messages",
    response_model=ChatMessagesResponse,
    operation_id="list_messages_in_chat",
    summary="List messages in a chat thread",
    description="Retrieve the message history for a specific chat thread with cursor-based pagination.",
    tags=["Message"],
)
async def get_messages(
    chat_id: str = Path(..., description="Chat ID"),
    agent_token: AgentToken = Depends(verify_agent_token),
    db: AsyncSession = Depends(get_db),
    cursor: Optional[str] = Query(
        None, description="Cursor for pagination (message id)"
    ),
    limit: int = Query(
        20, ge=1, le=100, description="Maximum number of messages to return"
    ),
) -> ChatMessagesResponse:
    """Get the message history for a chat thread with cursor-based pagination."""
    agent_id = agent_token.agent_id
    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
        )

    stmt = (
        select(ChatMessageTable)
        .where(
            ChatMessageTable.agent_id == agent_id, ChatMessageTable.chat_id == chat_id
        )
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


@router_rw.post(
    "/chats/{chat_id}/messages",
    response_model=List[ChatMessage],
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
    request: ChatMessageRequest,
    chat_id: str = Path(..., description="Chat ID"),
    agent_token: AgentToken = Depends(verify_agent_token),
):
    """Send a new message."""
    agent_id = agent_token.agent_id
    agent = await Agent.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Entity {agent_id} not found")

    real_user_id = get_real_user_id(agent_token, request.user_id, agent.owner)
    # Verify that the chat exists and belongs to the user
    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != agent_id or chat.user_id != real_user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
        )

    # Update summary if it's empty
    if not chat.summary:
        summary = textwrap.shorten(request.message, width=20, placeholder="...")
        await chat.update_summary(summary)

    # Increment the round count
    await chat.add_round()

    user_message = ChatMessageCreate(
        id=str(XID()),
        agent_id=agent_id,
        chat_id=chat_id,
        user_id=real_user_id,
        author_id=real_user_id,
        author_type=AuthorType.API,
        thread_type=AuthorType.API,
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
        app_id=request.app_id,
        search_mode=request.search_mode,
        super_mode=request.super_mode,
    )
    # Don't save the message here - let the handler save it
    # await user_message.save_in_session(db)

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


@router_rw.post(
    "/chats/{chat_id}/messages/retry",
    response_model=List[ChatMessage],
    operation_id="retry_message_in_chat",
    summary="Retry a message in a chat thread",
    description="Retry sending the last message in a specific chat thread. If the last message is from the system, returns all messages after the last user message. If the last message is from a user, generates a new response. Only works with non-streaming mode.",
    tags=["Message"],
)
async def retry_message(
    chat_id: str = Path(..., description="Chat ID"),
    user_id: Optional[str] = Query(
        None,
        description="User ID (optional). When provided (whether API key uses pk or sk), only public skills will be accessible.",
    ),
    agent_token: AgentToken = Depends(verify_agent_token),
    db: AsyncSession = Depends(get_db),
):
    """Retry the last message in a chat thread.

    If the last message is from the system, return all messages after the last user message.
    If the last message is from a user, generate a new response.
    Note: Retry only works in non-streaming mode.
    """
    agent_id = agent_token.agent_id
    # Get entity and check if exists
    agent = await Agent.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Entity {agent_id} not found")

    real_user_id = get_real_user_id(agent_token, user_id, agent.owner)
    # Verify that the chat exists and belongs to the user
    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != agent_id or chat.user_id != real_user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
        )

    last = await db.scalar(
        select(ChatMessageTable)
        .where(
            ChatMessageTable.agent_id == agent_id, ChatMessageTable.chat_id == chat_id
        )
        .order_by(desc(ChatMessageTable.created_at))
        .limit(1)
    )

    if not last:
        raise HTTPException(status_code=404, detail="No messages found")

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
                ChatMessageTable.agent_id == agent_id,
                ChatMessageTable.chat_id == chat_id,
                ChatMessageTable.author_type == AuthorType.API,
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
                ChatMessageTable.agent_id == agent_id,
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
            agent_id=agent_id,
            chat_id=chat_id,
            user_id=real_user_id,
            author_id=agent_id,
            thread_type=last_message.thread_type,
            reply_to=last_message.id,
            time_cost=0.0,
        )
        error_message = await error_message_create.save()
        return [last_message.sanitize_privacy(), error_message.sanitize_privacy()]

    # If last message is from user, generate a new response
    # Create a new user message for retry (non-streaming only)
    retry_user_message = ChatMessageCreate(
        id=str(XID()),
        agent_id=agent_id,
        chat_id=chat_id,
        user_id=real_user_id,
        author_id=real_user_id,
        author_type=AuthorType.API,
        thread_type=AuthorType.API,
        message=last_message.message,
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
        app_id=last_message.app_id,
        search_mode=last_message.search_mode,
        super_mode=last_message.super_mode,
    )

    # Execute handler (non-streaming mode only)
    response_messages = await execute_agent(retry_user_message)

    # Return messages list directly for compatibility with send_message
    return [message.sanitize_privacy() for message in response_messages]


@router_ro.get(
    "/messages/{message_id}",
    response_model=ChatMessage,
    operation_id="get_message_by_id",
    summary="Get message by ID",
    description="Retrieve a specific chat message by its ID for the current user. Returns 404 if not found or not owned by the user.",
    tags=["Message"],
)
async def get_message(
    message_id: str = Path(..., description="Message ID"),
    user_id: Optional[str] = Query(
        None,
        description="User ID (optional). When provided (whether API key uses pk or sk), only public skills will be accessible.",
    ),
    agent_token: AgentToken = Depends(verify_agent_token),
):
    """Get a specific message."""
    agent_id = agent_token.agent_id
    # Get agent to access owner
    agent = await Agent.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Entity {agent_id} not found")

    real_user_id = get_real_user_id(agent_token, user_id, agent.owner)
    message = await ChatMessage.get(message_id)
    if not message or message.user_id != real_user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Message not found"
        )
    return message.sanitize_privacy()


@router_ro.get(
    "/agent",
    response_model=AgentResponse,
    operation_id="get_current_agent",
    summary="Get current agent information",
    description="Retrieve the current agent's public information from the token.",
    tags=["Agent"],
)
async def get_current_agent(
    agent_token: AgentToken = Depends(verify_agent_token),
) -> Response:
    """Get the current agent from JWT token.

    **Returns:**
    * `AgentResponse` - Agent configuration with additional processed data

    **Raises:**
    * `HTTPException`:
        - 404: Agent not found
    """
    agent_id = agent_token.agent_id
    agent = await Agent.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get agent data
    agent_data = await AgentData.get(agent_id)

    agent_response = await AgentResponse.from_agent(agent, agent_data)

    # Return Response with ETag header
    return Response(
        content=agent_response.model_dump_json(),
        media_type="application/json",
        headers={"ETag": agent_response.etag()},
    )
