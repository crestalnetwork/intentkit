"""IntentKit Agent API Router.

This module provides the unified Agent API including:
- Authentication (AgentToken, verify_agent_token)
- Chat API (threads, messages)
- OpenAI-compatible Chat Completion API
"""

import logging
import textwrap
import time
from typing import Annotated, Any, ClassVar

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
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.db import get_db
from intentkit.core.agent import get_agent
from intentkit.core.engine import execute_agent, stream_agent
from intentkit.models.agent import AgentResponse
from intentkit.models.agent_data import AgentData
from intentkit.models.app_setting import SystemMessageType
from intentkit.models.chat import (
    AuthorType,
    Chat,
    ChatCreate,
    ChatMessage,
    ChatMessageAttachment,
    ChatMessageAttachmentType,
    ChatMessageCreate,
    ChatMessageTable,
)
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)

# =============================================================================
# Authentication
# =============================================================================


class AgentToken(BaseModel):
    """Agent token information."""

    agent_id: str
    is_public: bool


agent_security = HTTPBearer()


async def verify_agent_token(
    credentials: HTTPAuthorizationCredentials = Depends(agent_security),
) -> AgentToken:
    """Verify the API token and return the associated agent token information.

    Args:
        credentials: The Bearer token credentials from HTTPBearer

    Returns:
        AgentToken: The agent token information containing agent_id and is_public

    Raises:
        IntentKitAPIError: If token is invalid or agent not found
    """
    token = credentials.credentials

    # Find agent data by api_key
    agent_data = await AgentData.get_by_api_key(token)
    if not agent_data:
        raise IntentKitAPIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            key="InvalidAPIToken",
            message="Invalid API token",
        )

    # Check if token is public (starts with 'pk-')
    is_public = token.startswith("pk-")

    return AgentToken(agent_id=agent_data.id, is_public=is_public)


# =============================================================================
# Router
# =============================================================================

agent_api_router = APIRouter()


# =============================================================================
# Helper Functions
# =============================================================================


def get_real_user_id(
    agent_token: AgentToken, user_id: str | None, agent_owner: str | None
) -> str:
    """Generate real user_id based on agent token and user_id.

    Args:
        agent_token: Agent token containing agent_id and is_public flag
        user_id: Optional user ID
        agent_owner: Agent owner ID

    Returns:
        Real user ID string

    Raises:
        IntentKitAPIError: If user_id is provided for a private agent
    """
    if user_id:
        return f"{agent_token.agent_id}_{user_id}"
    else:
        if agent_token.is_public:
            return f"{agent_token.agent_id}_anonymous"
        else:
            return agent_owner or agent_token.agent_id


# =============================================================================
# Chat API Models
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


class ChatMessageRequest(BaseModel):
    """Request model for chat messages.

    This model represents the request body for creating a new chat message.
    It contains the necessary fields to identify the chat context and message
    content, along with optional attachments. The user ID is optional and
    combined with internal ID for storage if provided.
    """

    user_id: Annotated[
        str | None,
        Field(
            None,
            description="User ID (optional). When provided (whether API key uses pk or sk), only public skills will be accessible.",
            examples=["user-123"],
        ),
    ]
    app_id: Annotated[
        str | None,
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


# =============================================================================
# OpenAI Compatible API Models
# =============================================================================


class OpenAIMessage(BaseModel):
    """OpenAI message format."""

    role: str = Field(..., description="The role of the message author")
    content: str | list[dict[str, Any]] = Field(
        ..., description="The content of the message"
    )


class OpenAIChatCompletionRequest(BaseModel):
    """OpenAI Chat Completion API request format."""

    model: str = Field(..., description="ID of the model to use")
    messages: list[OpenAIMessage] = Field(
        ..., description="A list of messages comprising the conversation"
    )
    max_tokens: int | None = Field(
        None, description="The maximum number of tokens to generate"
    )
    temperature: float | None = Field(
        None, description="What sampling temperature to use"
    )
    top_p: float | None = Field(
        None, description="An alternative to sampling with temperature"
    )
    n: int | None = Field(
        None, description="How many chat completion choices to generate"
    )
    stream: bool | None = Field(
        None, description="If set, partial message deltas will be sent"
    )
    stop: str | list[str] | None = Field(
        None, description="Up to 4 sequences where the API will stop generating"
    )
    presence_penalty: float | None = Field(
        None, description="Number between -2.0 and 2.0"
    )
    frequency_penalty: float | None = Field(
        None, description="Number between -2.0 and 2.0"
    )
    logit_bias: dict[str, int] | None = Field(
        None, description="Modify the likelihood of specified tokens"
    )
    user: str | None = Field(
        None, description="A unique identifier representing your end-user"
    )
    response_format: dict[str, Any] | None = Field(
        None, description="An object specifying the format"
    )


class OpenAIUsage(BaseModel):
    """OpenAI usage statistics."""

    prompt_tokens: int = Field(0, description="Number of tokens in the prompt")
    completion_tokens: int = Field(0, description="Number of tokens in the completion")
    total_tokens: int = Field(0, description="Total number of tokens used")


class OpenAIDelta(BaseModel):
    """OpenAI delta object for streaming."""

    role: str | None = Field(None, description="The role of the message author")
    content: str | None = Field(None, description="The content of the message")


class OpenAIChoiceDelta(BaseModel):
    """OpenAI choice object for streaming."""

    index: int = Field(0, description="The index of the choice")
    delta: OpenAIDelta = Field(..., description="The delta object")
    finish_reason: str | None = Field(
        None, description="The reason the model stopped generating tokens"
    )


class OpenAIChatCompletionChunk(BaseModel):
    """OpenAI Chat Completion chunk for streaming."""

    id: str = Field(..., description="A unique identifier for the chat completion")
    object: str = Field("chat.completion.chunk", description="The object type")
    created: int = Field(
        ..., description="The Unix timestamp when the chat completion was created"
    )
    model: str = Field(..., description="The model used for the chat completion")
    choices: list[OpenAIChoiceDelta] = Field(
        ..., description="A list of chat completion choices"
    )
    system_fingerprint: str | None = Field(None, description="System fingerprint")


class OpenAIChoice(BaseModel):
    """OpenAI choice object."""

    index: int = Field(0, description="The index of the choice")
    message: OpenAIMessage = Field(..., description="The message object")
    finish_reason: str = Field(
        "stop", description="The reason the model stopped generating tokens"
    )


class OpenAIChatCompletionResponse(BaseModel):
    """OpenAI Chat Completion API response format."""

    id: str = Field(..., description="A unique identifier for the chat completion")
    object: str = Field("chat.completion", description="The object type")
    created: int = Field(
        ..., description="The Unix timestamp when the chat completion was created"
    )
    model: str = Field(..., description="The model used for the chat completion")
    choices: list[OpenAIChoice] = Field(
        ..., description="A list of chat completion choices"
    )
    usage: OpenAIUsage = Field(
        ..., description="Usage statistics for the completion request"
    )
    system_fingerprint: str | None = Field(None, description="System fingerprint")


# =============================================================================
# OpenAI Compatible API Helper Functions
# =============================================================================


def extract_text_and_images(
    content: str | list[dict[str, Any]],
) -> tuple[str, list[ChatMessageAttachment]]:
    """Extract text and images from OpenAI message content.

    Args:
        content: The message content (string or list of content parts)

    Returns:
        tuple: (text_content, list_of_attachments)
    """
    if isinstance(content, str):
        return content, []

    text_parts = []
    attachments = []

    for part in content:
        if part.get("type") == "text":
            text_parts.append(part.get("text", ""))
        elif part.get("type") == "image_url":
            image_url = part.get("image_url", {}).get("url", "")
            if image_url:
                attachments.append(
                    {
                        "type": ChatMessageAttachmentType.IMAGE,
                        "url": image_url,
                        "name": "image",
                    }
                )

    return " ".join(text_parts), attachments


def create_streaming_response(content: str, request_id: str, model: str, created: int):
    """Create a streaming response generator for OpenAI-compatible streaming.

    Args:
        content: The complete message content to stream
        request_id: The request ID
        model: The model name
        created: The creation timestamp

    Yields:
        str: Server-sent events formatted chunks
    """
    # First chunk with role
    first_chunk = OpenAIChatCompletionChunk(
        id=request_id,
        object="chat.completion.chunk",
        created=created,
        model=model,
        choices=[
            OpenAIChoiceDelta(
                index=0,
                delta=OpenAIDelta(role="assistant", content=None),
                finish_reason=None,
            )
        ],
        system_fingerprint=None,
    )
    yield f"data: {first_chunk.model_dump_json()}\n\n"

    # Content chunks - split content into smaller pieces for streaming effect
    chunk_size = 20  # Characters per chunk
    for i in range(0, len(content), chunk_size):
        chunk_content = content[i : i + chunk_size]
        content_chunk = OpenAIChatCompletionChunk(
            id=request_id,
            object="chat.completion.chunk",
            created=created,
            model=model,
            choices=[
                OpenAIChoiceDelta(
                    index=0,
                    delta=OpenAIDelta(role=None, content=chunk_content),
                    finish_reason=None,
                )
            ],
            system_fingerprint=None,
        )
        yield f"data: {content_chunk.model_dump_json()}\n\n"

    # Final chunk with finish_reason
    final_chunk = OpenAIChatCompletionChunk(
        id=request_id,
        object="chat.completion.chunk",
        created=created,
        model=model,
        choices=[
            OpenAIChoiceDelta(
                index=0,
                delta=OpenAIDelta(role=None, content=None),
                finish_reason="stop",
            )
        ],
        system_fingerprint=None,
    )
    yield f"data: {final_chunk.model_dump_json()}\n\n"

    # End of stream
    yield "data: [DONE]\n\n"


def create_streaming_response_batched(
    content_parts: list[str], request_id: str, model: str, created: int
):
    """Create a streaming response generator for OpenAI-compatible streaming with batched content.

    Args:
        content_parts: List of content parts to stream in batches
        request_id: The request ID
        model: The model name
        created: The creation timestamp

    Yields:
        str: Server-sent events formatted chunks
    """
    # First chunk with role
    first_chunk = OpenAIChatCompletionChunk(
        id=request_id,
        object="chat.completion.chunk",
        created=created,
        model=model,
        choices=[
            OpenAIChoiceDelta(
                index=0,
                delta=OpenAIDelta(role="assistant", content=None),
                finish_reason=None,
            )
        ],
        system_fingerprint=None,
    )
    yield f"data: {first_chunk.model_dump_json()}\n\n"

    # Stream each content part as a separate batch
    for i, content_part in enumerate(content_parts):
        if content_part:
            # Add newline between parts (except for the first one)
            if i > 0:
                newline_chunk = OpenAIChatCompletionChunk(
                    id=request_id,
                    object="chat.completion.chunk",
                    created=created,
                    model=model,
                    choices=[
                        OpenAIChoiceDelta(
                            index=0,
                            delta=OpenAIDelta(role=None, content="\n"),
                            finish_reason=None,
                        )
                    ],
                    system_fingerprint=None,
                )
                yield f"data: {newline_chunk.model_dump_json()}\n\n"

            # Stream the content part
            content_chunk = OpenAIChatCompletionChunk(
                id=request_id,
                object="chat.completion.chunk",
                created=created,
                model=model,
                choices=[
                    OpenAIChoiceDelta(
                        index=0,
                        delta=OpenAIDelta(role=None, content=content_part),
                        finish_reason=None,
                    )
                ],
                system_fingerprint=None,
            )
            yield f"data: {content_chunk.model_dump_json()}\n\n"

    # Final chunk with finish_reason
    final_chunk = OpenAIChatCompletionChunk(
        id=request_id,
        object="chat.completion.chunk",
        created=created,
        model=model,
        choices=[
            OpenAIChoiceDelta(
                index=0,
                delta=OpenAIDelta(role=None, content=None),
                finish_reason="stop",
            )
        ],
        system_fingerprint=None,
    )
    yield f"data: {final_chunk.model_dump_json()}\n\n"

    # End of stream
    yield "data: [DONE]\n\n"


# =============================================================================
# Chat API Endpoints
# =============================================================================


@agent_api_router.get(
    "/chats",
    response_model=list[Chat],
    operation_id="list_chats",
    summary="List chat threads",
    description="Retrieve all chat threads for the current user.",
    tags=["Thread"],
)
async def get_chats(
    user_id: str | None = Query(
        None,
        description="User ID (optional). When provided (whether API key uses pk or sk), only public skills will be accessible.",
    ),
    agent_token: AgentToken = Depends(verify_agent_token),
):
    """Get a list of chat threads."""
    agent_id = agent_token.agent_id
    # Get agent to access owner
    agent = await get_agent(agent_id)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message=f"Agent {agent_id} not found"
        )

    real_user_id = get_real_user_id(agent_token, user_id, agent.owner)
    return await Chat.get_by_agent_user(agent_id, real_user_id)


@agent_api_router.post(
    "/chats",
    response_model=Chat,
    operation_id="create_chat_thread",
    summary="Create a new chat thread",
    description="Create a new chat thread for a specific user.",
    tags=["Thread"],
)
async def create_chat(
    user_id: str | None = Query(
        None,
        description="User ID (optional). When provided (whether API key uses pk or sk), only public skills will be accessible.",
    ),
    agent_token: AgentToken = Depends(verify_agent_token),
):
    """Create a new chat thread."""
    agent_id = agent_token.agent_id
    # Verify that the entity exists
    agent = await get_agent(agent_id)
    if not agent:
        raise IntentKitAPIError(
            status_code=404,
            key="AgentNotFound",
            message=f"Agent {agent_id} not found",
        )

    real_user_id = get_real_user_id(agent_token, user_id, agent.owner)
    chat = ChatCreate(
        id=str(XID()),
        agent_id=agent_id,
        user_id=real_user_id,
        summary="",
        rounds=0,
    )
    _ = await chat.save()
    # Retrieve the full Chat object with auto-generated fields
    full_chat = await Chat.get(chat.id)
    return full_chat


@agent_api_router.get(
    "/chats/{chat_id}",
    response_model=Chat,
    operation_id="get_chat_thread_by_id",
    summary="Get chat thread by ID",
    description="Retrieve a specific chat thread by its ID for the current user. Returns 404 if not found or not owned by the user.",
    tags=["Thread"],
)
async def get_chat(
    chat_id: str = Path(..., description="Chat ID"),
    user_id: str | None = Query(
        None,
        description="User ID (optional). When provided (whether API key uses pk or sk), only public skills will be accessible.",
    ),
    agent_token: AgentToken = Depends(verify_agent_token),
):
    """Get a specific chat thread."""
    agent_id = agent_token.agent_id
    # Get agent to access owner
    agent = await get_agent(agent_id)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message=f"Agent {agent_id} not found"
        )

    real_user_id = get_real_user_id(agent_token, user_id, agent.owner)
    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != agent_id or chat.user_id != real_user_id:
        raise IntentKitAPIError(
            status_code=404, key="ChatNotFound", message="Chat not found"
        )
    return chat


@agent_api_router.patch(
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
        raise IntentKitAPIError(
            status_code=404, key="ChatNotFound", message="Chat not found"
        )

    # Update the summary field
    updated_chat = await chat.update_summary(request.summary)

    return updated_chat


@agent_api_router.delete(
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
        raise IntentKitAPIError(
            status_code=404, key="ChatNotFound", message="Chat not found"
        )
    await chat.delete()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@agent_api_router.get(
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
    cursor: str | None = Query(None, description="Cursor for pagination (message id)"),
    limit: int = Query(
        20, ge=1, le=100, description="Maximum number of messages to return"
    ),
) -> ChatMessagesResponse:
    """Get the message history for a chat thread with cursor-based pagination."""
    agent_id = agent_token.agent_id
    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != agent_id:
        raise IntentKitAPIError(
            status_code=404, key="ChatNotFound", message="Chat not found"
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


@agent_api_router.post(
    "/chats/{chat_id}/messages",
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
    request: ChatMessageRequest,
    chat_id: str = Path(..., description="Chat ID"),
    agent_token: AgentToken = Depends(verify_agent_token),
):
    """Send a new message."""
    agent_id = agent_token.agent_id
    agent = await get_agent(agent_id)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message=f"Agent {agent_id} not found"
        )

    real_user_id = get_real_user_id(agent_token, request.user_id, agent.owner)
    # Verify that the chat exists and belongs to the user
    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != agent_id or chat.user_id != real_user_id:
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


@agent_api_router.post(
    "/chats/{chat_id}/messages/retry",
    response_model=list[ChatMessage],
    operation_id="retry_message_in_chat",
    summary="Retry a message in a chat thread",
    description="Retry sending the last message in a specific chat thread. If the last message is from the system, returns all messages after the last user message. If the last message is from a user, generates a new response. Only works with non-streaming mode.",
    tags=["Message"],
)
async def retry_message(
    chat_id: str = Path(..., description="Chat ID"),
    user_id: str | None = Query(
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
    agent = await get_agent(agent_id)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message=f"Agent {agent_id} not found"
        )

    real_user_id = get_real_user_id(agent_token, user_id, agent.owner)
    # Verify that the chat exists and belongs to the user
    chat = await Chat.get(chat_id)
    if not chat or chat.agent_id != agent_id or chat.user_id != real_user_id:
        raise IntentKitAPIError(
            status_code=404, key="ChatNotFound", message="Chat not found"
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
            thread_type=last_message.thread_type or AuthorType.API,
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


@agent_api_router.get(
    "/messages/{message_id}",
    response_model=ChatMessage,
    operation_id="get_message_by_id",
    summary="Get message by ID",
    description="Retrieve a specific chat message by its ID for the current user. Returns 404 if not found or not owned by the user.",
    tags=["Message"],
)
async def get_message(
    message_id: str = Path(..., description="Message ID"),
    user_id: str | None = Query(
        None,
        description="User ID (optional). When provided (whether API key uses pk or sk), only public skills will be accessible.",
    ),
    agent_token: AgentToken = Depends(verify_agent_token),
):
    """Get a specific message."""
    agent_id = agent_token.agent_id
    # Get agent to access owner
    agent = await get_agent(agent_id)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message=f"Agent {agent_id} not found"
        )

    real_user_id = get_real_user_id(agent_token, user_id, agent.owner)
    message = await ChatMessage.get(message_id)
    if not message or message.user_id != real_user_id:
        raise IntentKitAPIError(
            status_code=404, key="MessageNotFound", message="Message not found"
        )
    return message.sanitize_privacy()


@agent_api_router.get(
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
    * `IntentKitAPIError`:
        - 404: Agent not found
    """
    agent_id = agent_token.agent_id
    agent = await get_agent(agent_id)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message=f"Agent {agent_id} not found"
        )

    # Get agent data
    agent_data = await AgentData.get(agent_id)

    agent_response = await AgentResponse.from_agent(agent, agent_data)

    # Return Response with ETag header
    return Response(
        content=agent_response.model_dump_json(),
        media_type="application/json",
        headers={"ETag": agent_response.etag()},
    )


# =============================================================================
# OpenAI Compatible API Endpoints
# =============================================================================


@agent_api_router.post(
    "/chat/completions",
    tags=["OpenAI"],
    operation_id="create_chat_completion",
    summary="Create chat completion",
)
async def create_chat_completion(
    request: OpenAIChatCompletionRequest,
    agent_token: AgentToken = Depends(verify_agent_token),
):
    """Create a chat completion using OpenAI-compatible API.

    This endpoint provides OpenAI Chat Completion API compatibility.
    Only the last message from the messages array is processed.

    Args:
        request: OpenAI chat completion request
        agent_token: The authenticated agent token information

    Returns:
        OpenAIChatCompletionResponse: OpenAI-compatible response
    """
    agent_id = agent_token.agent_id
    if not request.messages:
        raise IntentKitAPIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            key="EmptyMessages",
            message="Messages array cannot be empty",
        )

    # Get the last message only
    last_message = request.messages[-1]

    # Extract text and images from the message content
    text_content, attachments = extract_text_and_images(last_message.content)

    if not text_content.strip():
        raise IntentKitAPIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            key="EmptyContent",
            message="Message content cannot be empty",
        )

    # Get the agent to access its owner
    agent = await get_agent(agent_id)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message=f"Agent {agent_id} not found"
        )

    # Use agent owner or fallback to agent_id if owner is None
    if not agent_token.is_public and agent.owner:
        user_id = agent.owner
    else:
        user_id = agent_id + "_openai"

    # Create user message with fixed chat_id "api" and user_id as agent.owner
    user_message = ChatMessageCreate(
        id=str(XID()),
        agent_id=agent_id,
        chat_id="api",
        user_id=user_id,
        author_id=user_id,
        author_type=AuthorType.API,
        thread_type=AuthorType.API,
        message=text_content,
        attachments=attachments if attachments else None,
        model=None,
        reply_to=None,
        skill_calls=None,
        input_tokens=0,
        output_tokens=0,
        time_cost=0.0,
        credit_event_id=None,
        credit_cost=None,
        cold_start_cost=0.0,
        app_id=None,
        search_mode=None,
        super_mode=None,
    )

    # Execute agent
    response_messages = await execute_agent(user_message)

    # Process response messages based on AuthorType
    if not response_messages:
        raise IntentKitAPIError(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            key="NoResponse",
            message="No response from agent",
        )

    # Convert response messages to content list
    content_parts = []
    for msg in response_messages:
        if msg.author_type == AuthorType.AGENT or msg.author_type == AuthorType.SYSTEM:
            # For agent and system messages, use the content field
            if msg.message:
                content_parts.append(msg.message)
        elif msg.author_type == AuthorType.SKILL:
            # For skill messages, show "running skill_name..." for each skill call
            if msg.skill_calls and len(msg.skill_calls) > 0:
                for skill_call in msg.skill_calls:
                    skill_name = skill_call.get("name", "unknown")
                    content_parts.append(f"running {skill_name}...")
            else:
                content_parts.append("running unknown...")

    # Combine all content parts
    content = "\n".join(content_parts) if content_parts else ""

    # Create OpenAI-compatible response
    request_id = f"chatcmpl-{XID()}"
    created = int(time.time())

    # Check if streaming is requested
    if request.stream:
        # Return streaming response with batched content
        return StreamingResponse(
            create_streaming_response_batched(
                content_parts, request_id, request.model, created
            ),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/plain; charset=utf-8",
            },
        )
    else:
        # Return regular response
        response = OpenAIChatCompletionResponse(
            id=request_id,
            object="chat.completion",
            created=created,
            model=request.model,
            choices=[
                OpenAIChoice(
                    index=0,
                    message=OpenAIMessage(role="assistant", content=content),
                    finish_reason="stop",
                )
            ],
            usage=OpenAIUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            system_fingerprint=None,
        )

        logger.debug(f"OpenAI-compatible response: {response}")

        return response
