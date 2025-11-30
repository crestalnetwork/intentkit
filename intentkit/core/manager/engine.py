"""Streaming utilities for the on-demand manager agent."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator

from langgraph.graph.state import CompiledStateGraph

from intentkit.abstracts.graph import AgentContext, AgentState
from intentkit.core.engine import build_agent, stream_agent_raw
from intentkit.core.manager.skills import (
    get_agent_latest_draft_skill,
    get_agent_latest_public_info_skill,
    update_agent_draft_skill,
    update_public_info_skill,
)
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData
from intentkit.models.chat import ChatMessage, ChatMessageCreate

logger = logging.getLogger(__name__)


_MANAGER_CACHE_TTL = timedelta(hours=1)

_manager_executors: dict[
    str, CompiledStateGraph[AgentState, AgentContext, Any, Any]
] = {}
_manager_agents: dict[str, Agent] = {}
_manager_cached_at: dict[str, datetime] = {}


async def stream_manager(
    agent_id: str, user_id: str, message: ChatMessageCreate
) -> AsyncGenerator[ChatMessage, None]:
    """Stream chat messages for the manager agent of a specific agent."""

    executor, manager_agent, cold_start_cost = await _get_manager_executor(
        agent_id, user_id
    )

    if not message.agent_id:
        message.agent_id = manager_agent.id
    message.cold_start_cost = cold_start_cost

    async for chat_message in stream_agent_raw(message, manager_agent, executor):
        yield chat_message


def _build_manager_agent(agent_id: str, user_id: str) -> Agent:
    now = datetime.now(timezone.utc)

    # Get hierarchical skills text
    # skills_text = get_skills_hierarchical_text()

    prompt = (
        "### Create or Update Agent Draft.\n\n"
        "Use the available tools get_agent_latest_draft and update_agent_draft"
        " to review the latest draft, summarise updates, and propose modifications"
        " when necessary.\n"
        "Always explain what changed, why it changed, and whether any drafts"
        " were created or updated.\n"
        "When you update a draft, ensure the saved content remains consistent"
        " with the agent's purpose and principles.\n"
        "When a user makes a request to create or update an agent,"
        " you should always use skill get_agent_latest_draft to get the latest draft,"
        " then make changes from it and use skill update_agent_draft for the changes,"
        " remember the tool input data will only update the explicitly provided fields,"
        " at last summarize the changes to the user.\n"
        "The update_agent_draft function is efficient and safe, only updating fields you explicitly provide.\n"
        "If the field deployed_at of the latest draft is empty,"
        " it means the draft has not been deployed yet,"
        " and you should refuse requests such as autonomous management and agent analysis.\n\n"
        "\n\n### Avatar Generation\n\n"
        "The field `picture` in the agent draft is used to store the avatar image URL."
        "If the `picture` field is empty after a draft generation, you can ask user if they want to generate an avatar."
        "Use the `gpt_avatar_generator` skill to generate avatar-friendly images."
        "After get the avatar url from the skill result, you can update the `picture` field in the draft."
        "\n\n### Model Choice\n\n"
        "Use `gpt-5-mini` for normal requests, and `gpt-5` for complex requests."
        "If the user specified a model, call the `get_available_llms` skill to retrieve all"
        " available model IDs and find the closest match."
        "\n\n### Skill Configuration\n\n"
        """Because skills consume context, too much context can lead to a decline in LLM performance.
        Therefore, please use skills sparingly, ideally keeping the number below 20.
        If multiple skills are available for a single function, choose the one you deem most reliable.
        In a category, there are often many skills. Please select only the ones that are definitely useful.

        If a skill category's `api_key_provider` has only `agent_owner` as an option,
        then that skill will definitely require user input for the API key.
        You can suggest in your communication that the user manually configure it later,
        and avoid automatically generating drafts that use this skill.
        A typical skill configuration would look like this:
        ```
        "skills": {"category1": {"states": {"skill1": "public"}, "enabled": true}}
        ```
        The `enabled` flag is at the category level, and `states` refers to specific skills.
        For content involving sensitive material, select `private`. For content suitable for all users, select `public`.
        """
        "\n\n### Public Information\n\n"
        "Only agents that have already been deployed at least once can have their public"
        " information updated.\n"
        "The way to determine if it has been deployed at least once is to call `get_agent_latest_public_info`."
        "Public info is only required when preparing to publish an agent;"
        " private agents do not need it.\n"
        "Always call get_agent_latest_public_info before updating"
        " public info, and use update_public_info only when changes"
        " are necessary.\n"
        "The update_public_info function is efficient and safe, only updating fields you explicitly provide.\n\n"
        # "### Available Skills for Agent Configuration\n\n"
        # f"{skills_text}\n\n"
        # "When using the update_agent_draft tool, select skills from the list above based on the agent's requirements. "
        # "Use the exact skill names (e.g., 'erc20', 'common', 'twitter', etc.) when configuring the skills property. "
        # "Each skill can be enabled/disabled and configured with specific states and API key providers according to its schema."
    )

    agent_data = {
        "id": agent_id,
        "owner": user_id,
        "name": "Agent Manager",
        "purpose": "Assist with generating, updating, and reviewing agent drafts.",
        "personality": "Thorough, collaborative, and transparent about actions.",
        "principles": (
            "1. Keep the agent owner informed about every change.\n"
            "2. Preserve important context from prior drafts.\n"
            "3. Only modify drafts using the provided update tool.\n"
            "4. Speak to users in the language they ask their questions, but always use English in Agent Draft.\n"
            "5. When updating a draft, try to select the right skills. Don't pick too many, just enough to meet user needs.\n"
            "6. Update skill is override update, you must put the whole fields to input data, not only changed fields."
        ),
        "model": "grok-code-fast-1",
        "prompt": prompt,
        "prompt_append": None,
        "short_term_memory_strategy": "trim",
        "temperature": 0.2,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "skills": {
            "system": {
                "enabled": True,
                "states": {
                    "add_autonomous_task": "private",
                    "delete_autonomous_task": "private",
                    "edit_autonomous_task": "private",
                    "list_autonomous_tasks": "private",
                    "read_agent_api_key": "private",
                    "regenerate_agent_api_key": "private",
                    "get_available_llms": "private",
                },
            },
            "openai": {
                "enabled": True,
                "api_key_provider": "platform",
                "states": {
                    "gpt_avatar_generator": "private",
                },
            },
        },
        "created_at": now,
        "updated_at": now,
    }

    return Agent.model_validate(agent_data)


async def _get_manager_executor(
    agent_id: str, user_id: str
) -> tuple[CompiledStateGraph[AgentState, AgentContext, Any, Any], Agent, float]:
    now = datetime.now(timezone.utc)
    _cleanup_cache(now)

    cache_key = _cache_key(agent_id, user_id)
    executor = _manager_executors.get(cache_key)
    manager_agent = _manager_agents.get(cache_key)
    cold_start_cost = 0.0

    if not executor or not manager_agent:
        start = time.perf_counter()

        # Build manager agent if not cached
        if not manager_agent:
            manager_agent = _build_manager_agent(agent_id, user_id)
            _manager_agents[cache_key] = manager_agent

        # Build executor if not cached
        if not executor:
            custom_skills = [
                get_agent_latest_draft_skill,
                get_agent_latest_public_info_skill,
                update_agent_draft_skill,
                update_public_info_skill,
            ]
            executor = await build_agent(
                manager_agent, AgentData(id=manager_agent.id), custom_skills
            )
            _manager_executors[cache_key] = executor

        cold_start_cost = time.perf_counter() - start
        _manager_cached_at[cache_key] = now
        logger.info(
            "Initialized manager executor for agent %s and user %s", agent_id, user_id
        )
    else:
        _manager_cached_at[cache_key] = now

    return executor, manager_agent, cold_start_cost


def _cache_key(agent_id: str, user_id: str) -> str:
    return f"{agent_id}:{user_id}"


def _cleanup_cache(now: datetime) -> None:
    expired_before = now - _MANAGER_CACHE_TTL
    for cache_key, cached_time in list(_manager_cached_at.items()):
        if cached_time < expired_before:
            _manager_cached_at.pop(cache_key, None)
            _manager_executors.pop(cache_key, None)
            _manager_agents.pop(cache_key, None)
            logger.debug("Removed expired manager executor for %s", cache_key)
