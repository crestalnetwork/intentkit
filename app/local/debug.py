"""IntentKit Local Debug API Router.

This module provides debug endpoints for local development.
"""

import json
import logging

from fastapi import APIRouter, Path, Response
from fastapi.responses import PlainTextResponse

from intentkit.abstracts.graph import AgentContext
from intentkit.core.agent import get_agent
from intentkit.core.engine import thread_stats
from intentkit.core.prompt import agent_prompt
from intentkit.models.agent_data import AgentData
from intentkit.models.chat import AuthorType

# init logger
logger = logging.getLogger(__name__)

debug_router = APIRouter()


@debug_router.get(
    "/debug/{agent_id}/chats/{chat_id}/memory",
    tags=["Debug"],
    response_class=Response,
    operation_id="debug_chat_memory",
    summary="Chat Memory",
)
async def debug_chat_memory(
    agent_id: str = Path(..., description="Agent id"),
    chat_id: str = Path(..., description="Chat id"),
) -> Response:
    """Get chat memory for debugging."""
    messages = await thread_stats(agent_id, chat_id)
    # Convert messages to format JSON
    formatted_json = json.dumps(
        [message.model_dump() for message in messages], indent=4
    )
    return Response(content=formatted_json, media_type="application/json")


@debug_router.get(
    "/debug/{agent_id}/prompt",
    tags=["Debug"],
    response_class=PlainTextResponse,
    operation_id="debug_agent_prompt",
    summary="Agent Prompt",
)
async def debug_agent_prompt(
    agent_id: str = Path(..., description="Agent id"),
) -> str:
    """Get agent's init and append prompts for debugging."""
    agent = await get_agent(agent_id)
    if not agent:
        return "Agent not found"
    agent_data = await AgentData.get(agent_id)

    # Create a minimal context for debugging
    context = AgentContext(
        agent_id=agent_id,
        get_agent=lambda: agent,
        chat_id="debug",
        entrypoint=AuthorType.API,
        is_private=False,
    )

    init_prompt = agent_prompt(agent, agent_data, context)
    append_prompt = agent.prompt_append or "None"

    full_prompt = (
        f"[Init Prompt]\n\n{init_prompt}\n\n[Append Prompt]\n\n{append_prompt}"
    )
    return full_prompt
