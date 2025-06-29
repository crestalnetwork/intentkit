"""Core Client Module.

This module provides client functions for core API endpoints with environment-aware routing.
"""

import httpx

from intentkit.config.config import config
from intentkit.core.engine import execute_agent as local_execute_agent
from intentkit.models.chat import ChatMessage, ChatMessageCreate


async def execute_agent(
    message: ChatMessageCreate, debug: bool = False
) -> list[ChatMessage]:
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
        return await local_execute_agent(message, debug)

    # Make HTTP request in non-local environment
    url = f"{config.internal_base_url}/core/execute"
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json=message.model_dump(mode="json"),
            timeout=180,
        )
    response.raise_for_status()
    json_data = response.json()
    return [ChatMessage.model_validate(msg) for msg in json_data]
