"""Streaming utilities for the on-demand lead agent."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from intentkit.abstracts.graph import AgentContext, AgentState
from intentkit.core.engine import stream_agent_raw
from intentkit.core.executor import build_executor
from intentkit.core.lead.service import get_team_agents, verify_team_membership
from intentkit.core.lead.skills import (
    create_team_agent_skill,
    get_team_agent_skill,
    get_team_info_skill,
    lead_add_autonomous_task_skill,
    lead_delete_autonomous_task_skill,
    lead_edit_autonomous_task_skill,
    lead_get_available_llms_skill,
    lead_list_autonomous_tasks_skill,
    list_team_agents_skill,
    update_team_agent_skill,
)
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData
from intentkit.models.chat import ChatMessage, ChatMessageCreate
from intentkit.models.llm_picker import pick_default_model
from intentkit.models.team import Team
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


_LEAD_CACHE_TTL = timedelta(hours=1)

_lead_executors: dict[str, CompiledStateGraph[AgentState, AgentContext, Any, Any]] = {}
_lead_agents: dict[str, Agent] = {}
_lead_cached_at: dict[str, datetime] = {}


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
        "### Team Lead Agent\n\n"
        "You are the team lead agent that manages all agents in the team.\n"
        "You help team members create, configure, update, and monitor agents.\n\n"
        "### Workflow\n\n"
        "When a user starts a conversation, always call `lead_list_team_agents` first "
        "to understand the current team context and existing agents.\n\n"
        "### Agent Creation\n\n"
        "When creating a new agent, guide the user through:\n"
        "1. Name and purpose\n"
        "2. Model selection (use `gpt-5.4-mini` for normal, `gpt-5` for complex tasks; "
        "call `lead_get_available_llms` if user specifies a particular model)\n"
        "3. Skill configuration\n"
        "4. Additional settings as needed\n\n"
        "### Agent Updates\n\n"
        "Use `lead_update_team_agent` for direct deployment of changes (no draft flow).\n"
        "Always call `lead_get_team_agent` first to see the current config before updating.\n"
        "The update function is efficient and safe, only updating fields you explicitly provide.\n\n"
        "### Skill Configuration\n\n"
        "Because skills consume context, too much context can lead to a decline in LLM performance. "
        "Please use skills sparingly, ideally keeping the number below 20. "
        "If multiple skills are available for a single function, choose the most reliable one. "
        "In a category, there are often many skills. Please select only the ones that are definitely useful.\n\n"
        "A typical skill configuration looks like:\n"
        '```\n"skills": {"category1": {"states": {"skill1": "public"}, "enabled": true}}\n```\n'
        "The `enabled` flag is at the category level, and `states` refers to specific skills. "
        "For sensitive content, select `private`. For content suitable for all users, select `public`.\n\n"
        "### Agent Fields Reference\n\n"
        "- `name`: Display name (max 50 chars)\n"
        "- `purpose`: Purpose or role\n"
        "- `personality`: Personality traits\n"
        "- `principles`: Principles or values\n"
        "- `model`: LLM model ID\n"
        "- `prompt`: Base system prompt\n"
        "- `prompt_append`: Additional system prompt (higher priority)\n"
        "- `temperature`: Randomness (0.0~2.0, lower for rigorous tasks)\n"
        "- `skills`: Skill configurations dict\n"
        "- `slug`: URL-friendly slug (immutable once set)\n"
        "- `sub_agents`: List of sub-agent IDs or slugs\n"
        "- `sub_agent_prompt`: Instructions for how to use sub-agents\n"
        "- `enable_todo`: Enable todo list for complex multi-step tasks\n"
        "- `enable_activity`: Enable activity skills\n"
        "- `enable_post`: Enable post skills\n"
        "- `enable_long_term_memory`: Enable long-term memory\n"
        "- `super_mode`: Enable super mode with higher recursion limit\n"
        "- `search_internet`: Enable LLM native internet search\n"
        "- `visibility`: PRIVATE(0), TEAM(10), PUBLIC(20)\n"
    )

    owner = await Team.get_owner(team_id)
    if not owner:
        raise IntentKitAPIError(
            500, "TeamOwnerNotFound", f"Team '{team_id}' has no owner"
        )

    # Populate sub_agents with all active agents in the team
    team_agents = await get_team_agents(team_id)
    sub_agent_ids = [a.id for a in team_agents]

    agent_data = {
        "id": "team-" + team_id,
        "owner": owner,
        "team_id": team_id,
        "name": "Team Lead",
        "purpose": "Manage all agents in the team, create new agents, and assist team members.",
        "personality": "Organized, helpful, and proactive about team agent management.",
        "principles": (
            "1. Keep team members informed about every change.\n"
            "2. Always check existing agents before creating new ones.\n"
            "3. Use direct deployment (no draft flow) for all changes.\n"
            "4. Speak to users in the language they ask their questions, but always use English in Agent configuration.\n"
            "5. When configuring skills, be selective. Don't pick too many, just enough to meet user needs.\n"
            "6. Update skill is override update, you must put the whole fields to input data, not only changed fields."
        ),
        "model": pick_default_model(),
        "prompt": prompt,
        "prompt_append": None,
        "temperature": 0.2,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "search_internet": True,
        "super_mod": False,
        "enable_todo": False,
        "enable_activity": False,
        "enable_post": False,
        "enable_long_term_memory": True,
        "sub_agents": sub_agent_ids or None,
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
    _cleanup_cache(now)

    executor = _lead_executors.get(team_id)
    lead_agent = _lead_agents.get(team_id)
    cold_start_cost = 0.0

    if not executor or not lead_agent:
        start = time.perf_counter()

        if not lead_agent:
            lead_agent = await _build_lead_agent(team_id)
            _lead_agents[team_id] = lead_agent

        if not executor:
            custom_skills = [
                get_team_info_skill,
                list_team_agents_skill,
                create_team_agent_skill,
                get_team_agent_skill,
                update_team_agent_skill,
                lead_list_autonomous_tasks_skill,
                lead_add_autonomous_task_skill,
                lead_edit_autonomous_task_skill,
                lead_delete_autonomous_task_skill,
                lead_get_available_llms_skill,
            ]
            executor = await build_executor(
                lead_agent,
                AgentData.model_construct(id=lead_agent.id),
                custom_skills,
            )
            _lead_executors[team_id] = executor

        cold_start_cost = time.perf_counter() - start
        _lead_cached_at[team_id] = now
        logger.info("Initialized lead executor for team %s", team_id)
    else:
        _lead_cached_at[team_id] = now

    return executor, lead_agent, cold_start_cost


def invalidate_lead_cache(team_id: str) -> None:
    """Remove cached lead agent and executor for a team.

    Call this when the team's agent list changes (create, archive, reactivate)
    so the lead agent is rebuilt with an up-to-date sub_agents list.
    """
    _ = _lead_cached_at.pop(team_id, None)
    _ = _lead_executors.pop(team_id, None)
    _ = _lead_agents.pop(team_id, None)
    logger.debug("Invalidated lead cache for team %s", team_id)


def _cleanup_cache(now: datetime) -> None:
    """Evict expired lead cache entries.

    NOTE: This cleanup runs opportunistically on each request rather than via a
    separate scheduler. This is intentional — a dedicated periodic task would be
    too heavyweight for this use case.
    """
    expired_before = now - _LEAD_CACHE_TTL
    for cache_key, cached_time in list(_lead_cached_at.items()):
        if cached_time < expired_before:
            _ = _lead_cached_at.pop(cache_key, None)
            _ = _lead_executors.pop(cache_key, None)
            _ = _lead_agents.pop(cache_key, None)
            logger.debug("Removed expired lead executor for %s", cache_key)
