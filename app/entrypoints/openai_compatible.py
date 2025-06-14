import logging
from typing import Any, Dict, List, Optional

from epyxid import XID
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.core.engine import execute_agent
from models.agent import Agent
from models.agent_data import AgentData
from models.chat import (
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


# Dependency to verify token and get agent
async def verify_token(
    authorization: str = Header(..., alias="Authorization"),
) -> Agent:
    """Verify the API token and return the associated agent.

    Args:
        authorization: The Authorization header containing the Bearer token

    Returns:
        Agent: The agent associated with the token

    Raises:
        HTTPException: If token is invalid or agent not found
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected 'Bearer <token>'",
        )

    token = authorization[7:]  # Remove "Bearer " prefix

    # Find agent data by api_key
    agent_data = await AgentData.get_by_api_key(token)
    if not agent_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token"
        )

    # Get the agent
    agent = await Agent.get(agent_data.id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
        )

    return agent


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


@openai_router.post(
    "/v1/chat/completions",
    response_model=OpenAIChatCompletionResponse,
    tags=["Compatible"],
    operation_id="create_chat_completion",
    summary="Create chat completion",
)
async def create_chat_completion(
    request: OpenAIChatCompletionRequest, agent: Agent = Depends(verify_token)
) -> OpenAIChatCompletionResponse:
    """Create a chat completion using OpenAI-compatible API.

    This endpoint provides OpenAI Chat Completion API compatibility.
    Only the last message from the messages array is processed.

    Args:
        request: OpenAI chat completion request
        agent: The authenticated agent (from token verification)

    Returns:
        OpenAIChatCompletionResponse: OpenAI-compatible response
    """
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

    # Create user message with fixed chat_id "api" and user_id as agent.owner
    user_message = ChatMessageCreate(
        id=str(XID()),
        agent_id=agent.id,
        chat_id="api",
        user_id=agent.owner,
        author_id=agent.owner,
        author_type=AuthorType.API,
        thread_type=AuthorType.API,
        message=text_content,
        attachments=attachments if attachments else None,
    )

    # Execute agent
    response_messages = await execute_agent(user_message)

    # Get the last response message (should be from the agent)
    if not response_messages:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No response from agent",
        )

    agent_response = response_messages[-1]

    # Create OpenAI-compatible response
    import time

    response = OpenAIChatCompletionResponse(
        id=f"chatcmpl-{XID()}",
        object="chat.completion",
        created=int(time.time()),
        model=request.model,
        choices=[
            OpenAIChoice(
                index=0,
                message=OpenAIMessage(
                    role="assistant", content=agent_response.message or ""
                ),
                finish_reason="stop",
            )
        ],
        usage=OpenAIUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        system_fingerprint=None,
    )

    logger.debug(f"OpenAI-compatible response: {response}")

    return response
