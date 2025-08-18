"""Core API Router.

This module provides the core API endpoints for agent execution and management.
"""

from typing import Annotated

from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse
from pydantic import AfterValidator

from intentkit.core.engine import execute_agent, stream_agent
from intentkit.models.chat import ChatMessage, ChatMessageCreate

core_router = APIRouter(prefix="/core", tags=["Core"])


@core_router.post("/execute", response_model=list[ChatMessage])
async def execute(
    message: Annotated[
        ChatMessageCreate, AfterValidator(ChatMessageCreate.model_validate)
    ] = Body(
        ChatMessageCreate,
        description="The chat message containing agent_id, chat_id and message content",
    ),
) -> list[ChatMessage]:
    """Execute an agent with the provided message and return all results.

    This endpoint executes an agent with the provided message and returns all
    generated messages as a complete list after execution finishes.

    **Request Body:**
    * `message` - The chat message containing agent_id, chat_id and message content

    **Response:**
    Returns a list of ChatMessage objects containing:
    * Skill call results (including tool executions)
    * Agent reasoning and responses
    * System messages or error notifications

    **Returns:**
    * `list[ChatMessage]` - Complete list of response messages

    **Raises:**
    * `HTTPException`:
        - 400: If input parameters are invalid
        - 404: If agent not found
        - 500: For other server-side errors
    """
    return await execute_agent(message)


@core_router.post("/stream")
async def stream(
    message: Annotated[
        ChatMessageCreate, AfterValidator(ChatMessageCreate.model_validate)
    ] = Body(
        ChatMessageCreate,
        description="The chat message containing agent_id, chat_id and message content",
    ),
) -> StreamingResponse:
    """Stream agent execution results in real-time using Server-Sent Events.

    This endpoint executes an agent with the provided message and streams the results
    in real-time using the SSE (Server-Sent Events) standard format.

    **Request Body:**
    * `message` - The chat message containing agent_id, chat_id and message content

    **Stream Format:**
    The response uses Server-Sent Events with the following format:
    * Event type: `message`
    * Data: ChatMessage object as JSON
    * Format: `event: message\\ndata: {ChatMessage JSON}\\n\\n`

    **Response Content:**
    Each streamed message can be:
    * Skill call results (including tool executions)
    * Agent reasoning and responses
    * System messages or error notifications

    **Returns:**
    * `StreamingResponse` - SSE stream with real-time ChatMessage objects

    **Raises:**
    * `HTTPException`:
        - 400: If input parameters are invalid
        - 404: If agent not found
        - 500: For other server-side errors
    """

    async def generate():
        async for chat_message in stream_agent(message):
            yield f"event: message\ndata: {chat_message.model_dump_json()}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
