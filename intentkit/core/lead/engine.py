"""Streaming utilities for the on-demand lead agent."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from intentkit.abstracts.graph import AgentContext, AgentState
from intentkit.core.engine import stream_agent_raw
from intentkit.core.executor import build_executor
from intentkit.core.lead.cache import (
    cleanup_cache,
    lead_agents,
    lead_cached_at,
    lead_executors,
)
from intentkit.core.lead.constants import LEAD_DEFAULT_NAME, LEAD_DEFAULT_PERSONALITY
from intentkit.core.lead.service import verify_team_membership
from intentkit.core.lead.skills import (
    get_team_info_skill,
    list_team_agents_skill,
)
from intentkit.core.lead.skills.call_agent import lead_call_agent_skill
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData
from intentkit.models.chat import ChatMessage, ChatMessageCreate
from intentkit.models.llm_picker import pick_default_model
from intentkit.models.team import Team
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


async def get_lead_agent(team_id: str) -> Agent:
    """Get the lead agent for a team, using cache if available."""
    lead_agent = lead_agents.get(team_id)
    if not lead_agent:
        lead_agent = await _build_lead_agent(team_id)
    return lead_agent


async def stream_lead(
    team_id: str, user_id: str, message: ChatMessageCreate
) -> AsyncGenerator[ChatMessage, None]:
    """Stream chat messages for the lead agent of a team."""

    await verify_team_membership(team_id, user_id)

    executor, lead_agent, cold_start_cost = await _get_lead_executor(team_id)

    if not message.agent_id:
        message.agent_id = lead_agent.id
    if not message.team_id:
        message.team_id = team_id
    message.cold_start_cost = cold_start_cost

    async for chat_message in stream_agent_raw(message, lead_agent, executor):
        yield chat_message


async def _build_lead_agent(team_id: str) -> Agent:
    now = datetime.now(timezone.utc)

    prompt = (
        "### Sub-Agents\n\n"
        "Use `lead_call_agent` to delegate:\n\n"
        "- `agent-manager`: Agent CRUD.\n"
        "- `task-manager`: Autonomous task scheduling and management.\n"
        "- `self-updater`: Update your own name, avatar, personality, or memory.\n"
        "- `content-manager`: Read team activities and posts.\n\n"
        "You can also use `lead_call_agent` to delegate to any team agent "
        "discovered via `lead_list_team_agents`.\n\n"
        "### Workflow\n\n"
        "1. For casual chat or simple questions, answer directly.\n"
        "2. If the request fits one of the built-in sub-agents above, delegate it.\n"
        "3. For more complex requests, if `lead_list_team_agents` has not yet been "
        "called in this conversation, call it to see whether an existing team agent "
        "can handle the task, then delegate via `lead_call_agent`.\n"
        "4. If no existing agent fits, ask the user for permission to create one. "
        "Once approved, use `agent-manager` to create a suitable agent and delegate "
        "the task to it. Iterate on the agent's configuration as needed.\n"
        "5. If `agent-manager` cannot produce a working agent, or you hit "
        "authentication/account issues, ask the user for help.\n\n"
        "Note: always pass full user context when delegating, including agent "
        "IDs/names if provided.\n"
    )

    # Parallelize independent DB lookups
    owner, lead_config = await asyncio.gather(
        Team.get_owner(team_id),
        Team.get_lead_agent_config(team_id),
    )
    if not owner:
        raise IntentKitAPIError(
            500, "TeamOwnerNotFound", f"Team '{team_id}' has no owner"
        )
    lead_config = lead_config or {}

    agent_data = {
        "id": "team-" + team_id,
        "owner": owner,
        "team_id": team_id,
        "name": lead_config.get("name", LEAD_DEFAULT_NAME),
        "purpose": (
            "You are the lead of all agents in the team. Help human users in the "
            "team solve their problems — by using your own abilities, searching the "
            "internet, delegating to existing team agents, or creating new agents "
            "specialized for particular domains."
        ),
        "personality": lead_config.get("personality", LEAD_DEFAULT_PERSONALITY),
        "principles": "Speak to users in the language they ask their questions.",
        "model": pick_default_model(),
        "prompt": prompt,
        "prompt_append": None,
        "temperature": 0.5,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "search_internet": True,
        "super_mode": False,
        "enable_todo": False,
        "enable_activity": False,
        "enable_post": False,
        "enable_long_term_memory": True,
        "sub_agents": None,
        "skills": {
            "ui": {
                "enabled": True,
                "states": {
                    "ui_show_card": "private",
                    "ui_ask_user": "private",
                },
            },
        },
        "created_at": now,
        "updated_at": now,
    }

    agent = Agent.model_validate(agent_data)

    # Apply persisted avatar override
    if lead_config.get("avatar"):
        agent.picture = lead_config["avatar"]

    return agent


async def _get_lead_executor(
    team_id: str,
) -> tuple[CompiledStateGraph[AgentState, AgentContext, Any, Any], Agent, float]:
    now = datetime.now(timezone.utc)
    cleanup_cache(now)

    executor = lead_executors.get(team_id)
    lead_agent = lead_agents.get(team_id)
    cold_start_cost = 0.0

    if not executor or not lead_agent:
        start = time.perf_counter()

        # The executor needs a real AgentData so DynamicPromptMiddleware can
        # render long_term_memory into the system prompt. When both the agent
        # and executor are cold, fetch agent_data in parallel with the build.
        if not executor:
            if not lead_agent:
                lead_agent, agent_data = await asyncio.gather(
                    _build_lead_agent(team_id),
                    AgentData.get(f"team-{team_id}"),
                )
                lead_agents[team_id] = lead_agent
            else:
                agent_data = await AgentData.get(lead_agent.id)

            custom_skills = [
                lead_call_agent_skill,
                get_team_info_skill,
                list_team_agents_skill,
            ]
            executor = await build_executor(
                lead_agent,
                agent_data,
                custom_skills,
            )
            lead_executors[team_id] = executor
        elif not lead_agent:
            lead_agent = await _build_lead_agent(team_id)
            lead_agents[team_id] = lead_agent

        cold_start_cost = time.perf_counter() - start
        lead_cached_at[team_id] = now
        logger.info("Initialized lead executor for team %s", team_id)
    else:
        lead_cached_at[team_id] = now

    return executor, lead_agent, cold_start_cost
