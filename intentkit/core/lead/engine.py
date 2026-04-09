"""Streaming utilities for the on-demand lead agent."""

from __future__ import annotations

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
        "- `agent-manager`: Agent CRUD, LLM model info, skill listing.\n"
        "- `task-manager`: Autonomous task scheduling and management.\n\n"
        "### Workflow\n\n"
        "- Agent operations (create, configure, update, model/skill queries) "
        "→ `agent-manager`\n"
        "- Task management (schedule, edit, delete) → `task-manager`\n"
        "- Quick team overview → answer directly via "
        "`lead_get_team_info` or `lead_list_team_agents`\n"
        "- Pass full user context when delegating, including agent IDs/names if provided.\n"
    )

    owner = await Team.get_owner(team_id)
    if not owner:
        raise IntentKitAPIError(
            500, "TeamOwnerNotFound", f"Team '{team_id}' has no owner"
        )

    agent_data = {
        "id": "team-" + team_id,
        "owner": owner,
        "team_id": team_id,
        "name": "Team Lead",
        "purpose": "Coordinate sub-agents for team agent and task management.",
        "personality": "Helpful team assistant. Let sub-agents handle technical details.",
        "principles": "Speak to users in the language they ask their questions.",
        "model": pick_default_model(),
        "prompt": prompt,
        "prompt_append": None,
        "temperature": 0.2,
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

    return Agent.model_validate(agent_data)


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

        if not lead_agent:
            lead_agent = await _build_lead_agent(team_id)
            lead_agents[team_id] = lead_agent

        if not executor:
            custom_skills = [
                lead_call_agent_skill,
                get_team_info_skill,
                list_team_agents_skill,
            ]
            executor = await build_executor(
                lead_agent,
                AgentData.model_construct(id=lead_agent.id),
                custom_skills,
            )
            lead_executors[team_id] = executor

        cold_start_cost = time.perf_counter() - start
        lead_cached_at[team_id] = now
        logger.info("Initialized lead executor for team %s", team_id)
    else:
        lead_cached_at[team_id] = now

    return executor, lead_agent, cold_start_cost
