import logging
from typing import Any, Dict, List, Optional

from epyxid import XID
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.auth import AgentToken, verify_agent_token
from intentkit.core.engine import execute_agent
from intentkit.models.agent import Agent
from intentkit.models.chat import (
    AuthorType,
    ChatMessageAttachment,
    ChatMessageAttachmentType,
    ChatMessageCreate,
)

# init logger
logger = logging.getLogger(__name__)

openai_router = APIRouter()


# OpenAI API Models
class OpenAIMessage(BaseModel):
    """OpenAI message format."""

    role: str = Field(..., description="The role of the message author")
    content: str | List[Dict[str, Any]] = Field(
        ..., description="The content of the message"
    )


class OpenAIChatCompletionRequest(BaseModel):
    """OpenAI Chat Completion API request format."""

    model: str = Field(..., description="ID of the model to use")
    messages: List[OpenAIMessage] = Field(
        ..., description="A list of messages comprising the conversation"
    )
    max_tokens: Optional[int] = Field(
        None, description="The maximum number of tokens to generate"
    )
    temperature: Optional[float] = Field(
        None, description="What sampling temperature to use"
    )
    top_p: Optional[float] = Field(
        None, description="An alternative to sampling with temperature"
    )
    n: Optional[int] = Field(
        None, description="How many chat completion choices to generate"
    )
    stream: Optional[bool] = Field(
        None, description="If set, partial message deltas will be sent"
    )
    stop: Optional[str | List[str]] = Field(
        None, description="Up to 4 sequences where the API will stop generating"
    )
    presence_penalty: Optional[float] = Field(
        None, description="Number between -2.0 and 2.0"
    )
    frequency_penalty: Optional[float] = Field(
        None, description="Number between -2.0 and 2.0"
    )
    logit_bias: Optional[Dict[str, int]] = Field(
        None, description="Modify the likelihood of specified tokens"
    )
    user: Optional[str] = Field(
        None, description="A unique identifier representing your end-user"
    )
    response_format: Optional[Dict[str, Any]] = Field(
        None, description="An object specifying the format"
    )


class OpenAIUsage(BaseModel):
    """OpenAI usage statistics."""

    prompt_tokens: int = Field(0, description="Number of tokens in the prompt")
    completion_tokens: int = Field(0, description="Number of tokens in the completion")
    total_tokens: int = Field(0, description="Total number of tokens used")


class OpenAIDelta(BaseModel):
    """OpenAI delta object for streaming."""

    role: Optional[str] = Field(None, description="The role of the message author")
    content: Optional[str] = Field(None, description="The content of the message")


class OpenAIChoiceDelta(BaseModel):
    """OpenAI choice object for streaming."""

    index: int = Field(0, description="The index of the choice")
    delta: OpenAIDelta = Field(..., description="The delta object")
    finish_reason: Optional[str] = Field(
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
    choices: List[OpenAIChoiceDelta] = Field(
        ..., description="A list of chat completion choices"
    )
    system_fingerprint: Optional[str] = Field(None, description="System fingerprint")


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
    choices: List[OpenAIChoice] = Field(
        ..., description="A list of chat completion choices"
    )
    usage: OpenAIUsage = Field(
        ..., description="Usage statistics for the completion request"
    )
    system_fingerprint: Optional[str] = Field(None, description="System fingerprint")


def extract_text_and_images(
    content: str | List[Dict[str, Any]],
) -> tuple[str, List[ChatMessageAttachment]]:
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
    content_parts: List[str], request_id: str, model: str, created: int
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


@openai_router.post(
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Messages array cannot be empty",
        )

    # Get the last message only
    last_message = request.messages[-1]

    # Extract text and images from the message content
    text_content, attachments = extract_text_and_images(last_message.content)

    if not text_content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty",
        )

    # Get the agent to access its owner
    agent = await Agent.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No response from agent",
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
    import time

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
