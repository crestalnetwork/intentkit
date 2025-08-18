"""Core Client Module.

This module provides client functions for core API endpoints with environment-aware routing.
"""

from typing import AsyncIterator

import httpx

from intentkit.config.config import config
from intentkit.core.engine import execute_agent as local_execute_agent
from intentkit.core.engine import stream_agent as local_stream_agent
from intentkit.models.chat import ChatMessage, ChatMessageCreate


async def execute_agent(message: ChatMessageCreate) -> list[ChatMessage]:
    """Execute an agent with environment-aware routing.

    In local environment, directly calls the local execute_agent function.
    In other environments, makes HTTP request to the core API endpoint.

    Args:
        message (ChatMessage): The chat message containing agent_id, chat_id and message content
        debug (bool): Enable debug mode

    Returns:
        list[ChatMessage]: Formatted response lines from agent execution

    Raises:
        HTTPException: For API errors (in non-local environment)
        Exception: For other execution errors
    """
    if config.env == "local":
        return await local_execute_agent(message)

    # Make HTTP request in non-local environment
    url = f"{config.internal_base_url}/core/execute"
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json=message.model_dump(mode="json"),
            timeout=300,
        )
    response.raise_for_status()
    json_data = response.json()
    return [ChatMessage.model_validate(msg) for msg in json_data]


async def stream_agent(message: ChatMessageCreate) -> AsyncIterator[ChatMessage]:
    """Stream agent execution with environment-aware routing using Server-Sent Events.

    In local environment, directly calls the local stream_agent function.
    In other environments, makes HTTP request to the core stream API endpoint and parses SSE format.

    Args:
        message (ChatMessageCreate): The chat message containing agent_id, chat_id and message content
        debug (bool): Enable debug mode

    Yields:
        ChatMessage: Individual response messages from agent execution

    Raises:
        HTTPException: For API errors (in non-local environment)
        Exception: For other execution errors
    """
    if config.env == "local":
        async for chat_message in local_stream_agent(message):
            yield chat_message
        return

    # Make HTTP request in non-local environment
    url = f"{config.internal_base_url}/core/stream"
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            url,
            json=message.model_dump(mode="json"),
            timeout=300,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    json_str = line[6:]  # Remove "data: " prefix
                    if json_str.strip():
                        yield ChatMessage.model_validate_json(json_str)
