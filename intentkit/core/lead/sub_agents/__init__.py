"""Lead sub-agents registry and executor caching."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from intentkit.abstracts.graph import AgentContext, AgentState
from intentkit.core.executor import build_executor
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData

logger = logging.getLogger(__name__)

# Sub-agent slug constants
SLUG_AGENT_MANAGER = "agent-manager"
SLUG_TASK_MANAGER = "task-manager"
SLUG_SELF_UPDATER = "self-updater"
SLUG_CONTENT_MANAGER = "content-manager"


@dataclass
class SubAgentDefinition:
    """Definition of an in-memory sub-agent."""

    slug: str
    description: str
    build_fn: Callable[[str], Agent]  # (team_id) -> Agent
    skills_fn: Callable[[], Sequence[BaseTool]]  # () -> skills list


# Caches keyed by "team_id:slug"
_sub_executors: dict[str, CompiledStateGraph[AgentState, AgentContext, Any, Any]] = {}
_sub_agents: dict[str, Agent] = {}
_sub_cached_at: dict[str, datetime] = {}


def _cache_key(team_id: str, slug: str) -> str:
    return f"{team_id}:{slug}"


async def get_sub_agent_executor(
    team_id: str, slug: str
) -> tuple[CompiledStateGraph[AgentState, AgentContext, Any, Any], Agent]:
    """Get or build a sub-agent executor, using cache if available."""
    key = _cache_key(team_id, slug)

    executor = _sub_executors.get(key)
    agent = _sub_agents.get(key)

    if executor and agent:
        _sub_cached_at[key] = datetime.now(timezone.utc)
        return executor, agent

    definition = SUB_AGENT_REGISTRY[slug]
    agent = definition.build_fn(team_id)
    skills = definition.skills_fn()

    executor = await build_executor(
        agent,
        AgentData.model_construct(id=agent.id),
        skills,
    )

    _sub_executors[key] = executor
    _sub_agents[key] = agent
    _sub_cached_at[key] = datetime.now(timezone.utc)
    logger.info("Built sub-agent executor %s for team %s", slug, team_id)

    return executor, agent


def invalidate_sub_agent_caches(team_id: str) -> None:
    """Evict all sub-agent caches for a team."""
    for slug in SUB_AGENT_REGISTRY:
        key = _cache_key(team_id, slug)
        _sub_executors.pop(key, None)
        _sub_agents.pop(key, None)
        _sub_cached_at.pop(key, None)


def cleanup_sub_agent_caches(expired_before: datetime) -> None:
    """Evict expired sub-agent cache entries."""
    for key, cached_time in list(_sub_cached_at.items()):
        if cached_time < expired_before:
            _sub_executors.pop(key, None)
            _sub_agents.pop(key, None)
            _sub_cached_at.pop(key, None)
            logger.debug("Removed expired sub-agent executor %s", key)


# Registry populated after imports to avoid circular deps
from intentkit.core.lead.sub_agents.agent_manager import (  # noqa: E402
    build_agent_manager,
    get_agent_manager_skills,
)
from intentkit.core.lead.sub_agents.content_manager import (  # noqa: E402
    build_content_manager,
    get_content_manager_skills,
)
from intentkit.core.lead.sub_agents.self_updater import (  # noqa: E402
    build_self_updater,
    get_self_updater_skills,
)
from intentkit.core.lead.sub_agents.task_manager import (  # noqa: E402
    build_task_manager,
    get_task_manager_skills,
)

SUB_AGENT_REGISTRY: dict[str, SubAgentDefinition] = {
    SLUG_AGENT_MANAGER: SubAgentDefinition(
        slug=SLUG_AGENT_MANAGER,
        description=(
            "Manages team agents: create, update, configure, list agents. "
            "Also provides LLM model info and available skills for agent configuration."
        ),
        build_fn=build_agent_manager,
        skills_fn=get_agent_manager_skills,
    ),
    SLUG_TASK_MANAGER: SubAgentDefinition(
        slug=SLUG_TASK_MANAGER,
        description=(
            "Manages autonomous tasks: list, add, edit, delete scheduled tasks for agents."
        ),
        build_fn=build_task_manager,
        skills_fn=get_task_manager_skills,
    ),
    SLUG_SELF_UPDATER: SubAgentDefinition(
        slug=SLUG_SELF_UPDATER,
        description=(
            "Updates the lead agent itself: name, avatar, personality, and memory."
        ),
        build_fn=build_self_updater,
        skills_fn=get_self_updater_skills,
    ),
    SLUG_CONTENT_MANAGER: SubAgentDefinition(
        slug=SLUG_CONTENT_MANAGER,
        description=(
            "Reads team content: recent activities, post listings, and full post content."
        ),
        build_fn=build_content_manager,
        skills_fn=get_content_manager_skills,
    ),
}
