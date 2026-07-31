"""Lead sub-agents registry and executor caching."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from intentkit.abstracts.graph import AgentContext, AgentState

# Sub-agent cache storage lives in core.caches so the lead cache sweep can evict
# these entries without importing this package (that closed an import cycle).
from intentkit.core.caches import sub_agents as _sub_agents
from intentkit.core.caches import sub_cache_key as _cache_key
from intentkit.core.caches import sub_cached_at as _sub_cached_at
from intentkit.core.caches import sub_executors as _sub_executors
from intentkit.core.executor import build_executor
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData

logger = logging.getLogger(__name__)

# Sub-agent slug constants
SLUG_AGENT_MANAGER = "agent-manager"
SLUG_TASK_MANAGER = "task-manager"
SLUG_SELF_UPDATER = "self-updater"
SLUG_CONTENT_MANAGER = "content-manager"
SLUG_USER_MANAGER = "user-manager"


@dataclass
class SubAgentDefinition:
    """Definition of an in-memory sub-agent."""

    slug: str
    description: str
    build_fn: Callable[[str], Agent]  # (team_id) -> Agent
    tools_fn: Callable[[], Sequence[BaseTool]]  # () -> tools list


async def get_sub_agent_executor(
    team_id: str, slug: str
) -> tuple[CompiledStateGraph[AgentState, AgentContext, Any, Any], Agent]:
    """Get or build a sub-agent executor, using cache if available."""
    key = _cache_key(team_id, slug)

    executor = _sub_executors.get(key)
    agent = _sub_agents.get(key)

    if executor and agent:
        _sub_cached_at[key] = datetime.now(UTC)
        return executor, agent

    definition = SUB_AGENT_REGISTRY[slug]
    agent = definition.build_fn(team_id)
    tools = definition.tools_fn()

    executor = await build_executor(
        agent,
        AgentData.model_construct(id=agent.id),
        tools,
    )

    _sub_executors[key] = executor
    _sub_agents[key] = agent
    _sub_cached_at[key] = datetime.now(UTC)
    logger.info("Built sub-agent executor %s for team %s", slug, team_id)

    return executor, agent


def invalidate_sub_agent_caches(team_id: str) -> None:
    """Evict all sub-agent caches for a team."""
    for slug in SUB_AGENT_REGISTRY:
        key = _cache_key(team_id, slug)
        _sub_executors.pop(key, None)
        _sub_agents.pop(key, None)
        _sub_cached_at.pop(key, None)


# Registry populated after imports to avoid circular deps
from intentkit.core.lead.sub_agents.agent_manager import (  # noqa: E402
    build_agent_manager,
    get_agent_manager_tools,
)
from intentkit.core.lead.sub_agents.content_manager import (  # noqa: E402
    build_content_manager,
    get_content_manager_tools,
)
from intentkit.core.lead.sub_agents.self_updater import (  # noqa: E402
    build_self_updater,
    get_self_updater_tools,
)
from intentkit.core.lead.sub_agents.task_manager import (  # noqa: E402
    build_task_manager,
    get_task_manager_tools,
)
from intentkit.core.lead.sub_agents.user_manager import (  # noqa: E402
    build_user_manager,
    get_user_manager_tools,
)

SUB_AGENT_REGISTRY: dict[str, SubAgentDefinition] = {
    SLUG_AGENT_MANAGER: SubAgentDefinition(
        slug=SLUG_AGENT_MANAGER,
        description=(
            "Manages team agents end-to-end: create, update, configure, and list "
            "agents. Also exposes LLM model info and available tools for agent "
            "configuration."
        ),
        build_fn=build_agent_manager,
        tools_fn=get_agent_manager_tools,
    ),
    SLUG_TASK_MANAGER: SubAgentDefinition(
        slug=SLUG_TASK_MANAGER,
        description=(
            "Schedules and manages the team's autonomous (cron) tasks: list, "
            "add, edit, and delete tasks, and choose which agent each task targets."
        ),
        build_fn=build_task_manager,
        tools_fn=get_task_manager_tools,
    ),
    SLUG_SELF_UPDATER: SubAgentDefinition(
        slug=SLUG_SELF_UPDATER,
        description=(
            "Updates the lead agent itself: name, avatar, personality, and memory."
        ),
        build_fn=build_self_updater,
        tools_fn=get_self_updater_tools,
    ),
    SLUG_CONTENT_MANAGER: SubAgentDefinition(
        slug=SLUG_CONTENT_MANAGER,
        description=(
            "Reads team content: recent activities, post listings, and full post content."
        ),
        build_fn=build_content_manager,
        tools_fn=get_content_manager_tools,
    ),
    SLUG_USER_MANAGER: SubAgentDefinition(
        slug=SLUG_USER_MANAGER,
        description=("Manages the current user's profile: name, timezone, language."),
        build_fn=build_user_manager,
        tools_fn=get_user_manager_tools,
    ),
}
