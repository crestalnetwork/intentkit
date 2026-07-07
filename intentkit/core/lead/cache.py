"""Lead agent cache management."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from intentkit.abstracts.graph import AgentContext, AgentState
from intentkit.models.agent import Agent

logger = logging.getLogger(__name__)

_LEAD_CACHE_TTL = timedelta(hours=1)

# Keyed by lead_cache_key(team_id, user_id): the executor's toolset and prompt
# include the requesting user's own user-level links, so each (team, user)
# pair gets its own entry.
lead_executors: dict[str, CompiledStateGraph[AgentState, AgentContext, Any, Any]] = {}
lead_agents: dict[str, Agent] = {}
lead_cached_at: dict[str, datetime] = {}


def lead_cache_key(team_id: str, user_id: str) -> str:
    """The lead cache key for one user's conversations with a team's lead.

    Team ids never contain ``|`` (validated slug format), so
    ``lead_cache_prefix`` unambiguously scopes a team's entries.
    """
    return f"{team_id}|{user_id}"


def lead_cache_prefix(team_id: str) -> str:
    """The key prefix shared by all of a team's per-user cache entries."""
    return f"{team_id}|"


def any_lead_executor(
    team_id: str,
) -> CompiledStateGraph[AgentState, AgentContext, Any, Any] | None:
    """Any cached lead executor of the team, regardless of user.

    ONLY for callers that need a graph of the right shape (e.g. appending a
    message to a shared-checkpointer thread). Never run agent turns on it —
    its toolset and prompt belong to whichever user's entry happened to be
    returned.
    """
    prefix = lead_cache_prefix(team_id)
    for key, executor in lead_executors.items():
        if key.startswith(prefix):
            return executor
    return None


def invalidate_lead_cache(team_id: str, user_id: str | None = None) -> None:
    """Remove cached lead agents and executors of a team.

    With ``user_id``, only that user's entry is dropped — right for
    user-level link changes, which don't affect other users' toolsets or the
    user-agnostic display agent. Without it, everything of the team goes: the
    per-user entries and the bare-team-id user-agnostic agent.

    Call this when the team's agent list changes (create, archive,
    reactivate) or its links change. Sub-agent caches are NOT invalidated
    here because sub-agents are static definitions that don't depend on the
    team's agent list.
    """
    if user_id is not None:
        key = lead_cache_key(team_id, user_id)
        for cache in (lead_cached_at, lead_executors, lead_agents):
            _ = cache.pop(key, None)
        logger.debug("Invalidated lead cache for team %s user %s", team_id, user_id)
        return
    prefix = lead_cache_prefix(team_id)
    for cache in (lead_cached_at, lead_executors, lead_agents):
        # k == team_id also drops the user-agnostic display entry.
        for key in [k for k in cache if k == team_id or k.startswith(prefix)]:
            _ = cache.pop(key, None)
    logger.debug("Invalidated lead cache for team %s", team_id)


def cleanup_cache(now: datetime) -> None:
    """Evict expired lead cache entries.

    NOTE: This cleanup runs opportunistically on each request rather than via a
    separate scheduler. This is intentional — a dedicated periodic task would be
    too heavyweight for this use case.
    """
    expired_before = now - _LEAD_CACHE_TTL
    # Keys are both per-user ("{team_id}|{user_id}") and bare team ids (the
    # user-agnostic display agent); each carries its own cached_at.
    for cache_key, cached_time in list(lead_cached_at.items()):
        if cached_time < expired_before:
            _ = lead_cached_at.pop(cache_key, None)
            _ = lead_executors.pop(cache_key, None)
            _ = lead_agents.pop(cache_key, None)
            logger.debug("Removed expired lead executor for %s", cache_key)

    from intentkit.core.lead.sub_agents import cleanup_sub_agent_caches

    cleanup_sub_agent_caches(expired_before)
