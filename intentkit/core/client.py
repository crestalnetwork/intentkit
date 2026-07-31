"""Core Client Module.

This module provides client functions for core API endpoints with environment-aware routing.
"""

from collections.abc import AsyncIterator

import httpx

from intentkit.config.config import config
from intentkit.core.engine import execute_agent as local_execute_agent
from intentkit.core.engine import stream_agent as local_stream_agent
from intentkit.core.lead.engine import execute_lead as local_execute_lead
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
            timeout=1800,
        )
    response.raise_for_status()
    json_data = response.json()
    return [ChatMessage.model_validate(msg) for msg in json_data]


async def execute_lead(
    team_id: str, user_id: str, message: ChatMessageCreate
) -> list[ChatMessage]:
    """Execute a team lead with environment-aware routing.

    Mirrors :func:`execute_agent`: runs in-process in the local environment,
    otherwise calls the internal core API so the caller (e.g. the autonomous
    scheduler) doesn't build executors in its own process.
    """
    if config.env == "local":
        return await local_execute_lead(team_id, user_id, message)

    url = f"{config.internal_base_url}/core/execute-lead"
    payload = {
        "team_id": team_id,
        "user_id": user_id,
        "message": message.model_dump(mode="json"),
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=1800)
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
    async with (
        httpx.AsyncClient() as client,
        client.stream(
            "POST",
            url,
            json=message.model_dump(mode="json"),
            timeout=300,
        ) as response,
    ):
        response.raise_for_status()
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                json_str = line[6:]  # Remove "data: " prefix
                if json_str.strip():
                    yield ChatMessage.model_validate_json(json_str)
