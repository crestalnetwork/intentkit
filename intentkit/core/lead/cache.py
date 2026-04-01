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

lead_executors: dict[str, CompiledStateGraph[AgentState, AgentContext, Any, Any]] = {}
lead_agents: dict[str, Agent] = {}
lead_cached_at: dict[str, datetime] = {}


def invalidate_lead_cache(team_id: str) -> None:
    """Remove cached lead agent and executor for a team.

    Call this when the team's agent list changes (create, archive, reactivate)
    so the lead agent is rebuilt with an up-to-date sub_agents list.
    """
    _ = lead_cached_at.pop(team_id, None)
    _ = lead_executors.pop(team_id, None)
    _ = lead_agents.pop(team_id, None)
    logger.debug("Invalidated lead cache for team %s", team_id)


def cleanup_cache(now: datetime) -> None:
    """Evict expired lead cache entries.

    NOTE: This cleanup runs opportunistically on each request rather than via a
    separate scheduler. This is intentional — a dedicated periodic task would be
    too heavyweight for this use case.
    """
    expired_before = now - _LEAD_CACHE_TTL
    for cache_key, cached_time in list(lead_cached_at.items()):
        if cached_time < expired_before:
            _ = lead_cached_at.pop(cache_key, None)
            _ = lead_executors.pop(cache_key, None)
            _ = lead_agents.pop(cache_key, None)
            logger.debug("Removed expired lead executor for %s", cache_key)
