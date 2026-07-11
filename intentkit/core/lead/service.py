"""Team utilities for the lead agent."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import func, or_, select

from intentkit.config.db import get_session
from intentkit.models.agent import Agent
from intentkit.models.agent.core import AgentVisibility
from intentkit.models.agent.db import AgentTable
from intentkit.models.team import TeamMemberTable
from intentkit.models.team_feed import TeamSubscriptionTable
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


async def verify_team_membership(team_id: str, user_id: str) -> None:
    """Raise 403 if user is not a member of the team."""
    async with get_session() as db:
        stmt = select(TeamMemberTable).where(
            TeamMemberTable.team_id == team_id,
            TeamMemberTable.user_id == user_id,
        )
        member = await db.scalar(stmt)
        if not member:
            raise IntentKitAPIError(403, "Forbidden", "Not a member of this team")


async def get_team_agents(team_id: str) -> list[Agent]:
    """Query AgentTable where team_id matches, exclude archived, order by created_at desc."""
    async with get_session() as db:
        stmt = (
            select(AgentTable)
            .where(
                AgentTable.team_id == team_id,
                AgentTable.archived_at.is_(None),
            )
            .order_by(AgentTable.created_at.desc())
        )
        result = await db.scalars(stmt)
        return [Agent.model_validate(row) for row in result]


async def list_public_agents(search: str | None = None, limit: int = 30) -> list[Agent]:
    """List public agents from across the platform.

    Returns agents with ``visibility >= PUBLIC`` that are not archived, newest
    first. ``search`` filters by name/description substring (case-insensitive).
    """
    async with get_session() as db:
        stmt = select(AgentTable).where(
            AgentTable.visibility >= AgentVisibility.PUBLIC,
            AgentTable.archived_at.is_(None),
        )
        if search:
            like = f"%{search}%"
            stmt = stmt.where(
                or_(AgentTable.name.ilike(like), AgentTable.description.ilike(like))
            )
        stmt = stmt.order_by(AgentTable.created_at.desc()).limit(limit)
        result = await db.scalars(stmt)
        return [Agent.model_validate(row) for row in result]


async def get_followed_agent_ids(team_id: str) -> set[str]:
    """Return the set of agent IDs a team follows (subscribes to)."""
    async with get_session() as db:
        result = await db.scalars(
            select(TeamSubscriptionTable.agent_id).where(
                TeamSubscriptionTable.team_id == team_id
            )
        )
        return set(result)


async def is_agent_followed(team_id: str, agent_id: str) -> bool:
    """Return whether a team follows (subscribes to) a specific agent."""
    async with get_session() as db:
        row = await db.scalar(
            select(TeamSubscriptionTable.agent_id).where(
                TeamSubscriptionTable.team_id == team_id,
                TeamSubscriptionTable.agent_id == agent_id,
            )
        )
        return row is not None


async def get_followed_external_agents(team_id: str) -> list[Agent]:
    """Return public agents the team follows that belong to OTHER teams.

    A team auto-subscribes to its own agents for the content feed; those are
    excluded here because they are already reachable via ``get_team_agents``.
    This returns the external public agents a team has explicitly followed, for
    injection into the lead's system prompt and delegation via lead_call_agent.
    """
    async with get_session() as db:
        stmt = (
            select(AgentTable)
            .join(
                TeamSubscriptionTable,
                TeamSubscriptionTable.agent_id == AgentTable.id,
            )
            .where(
                TeamSubscriptionTable.team_id == team_id,
                AgentTable.team_id != team_id,
                AgentTable.visibility >= AgentVisibility.PUBLIC,
                AgentTable.archived_at.is_(None),
            )
            .order_by(TeamSubscriptionTable.subscribed_at.desc())
        )
        result = await db.scalars(stmt)
        return [Agent.model_validate(row) for row in result]


async def _count_team_public_agents(team_id: str) -> int:
    async with get_session() as db:
        return (
            await db.scalar(
                select(func.count(AgentTable.id)).where(
                    AgentTable.team_id == team_id,
                    AgentTable.visibility >= AgentVisibility.PUBLIC,
                    AgentTable.archived_at.is_(None),
                )
            )
            or 0
        )


async def get_team_with_members(team_id: str) -> dict[str, Any]:
    """Return team info + members list + public-agent quota usage."""
    from intentkit.core.team.membership import get_members, get_team

    team = await get_team(team_id)
    if not team:
        raise IntentKitAPIError(404, "TeamNotFound", f"Team '{team_id}' not found")

    members, current_public_agent_count = await asyncio.gather(
        get_members(team_id),
        _count_team_public_agents(team_id),
    )

    return {
        "id": team.id,
        "name": team.name,
        "avatar": team.avatar,
        "created_at": team.created_at.isoformat() if team.created_at else None,
        "members": [m.model_dump(mode="json") for m in members],
        "public_agent_limit": team.public_agent_limit,
        "current_public_agent_count": current_public_agent_count,
    }


async def verify_agent_in_team(agent_id: str, team_id: str) -> Agent:
    """Get agent, verify it belongs to team. Raise 404/403 on failure."""
    async with get_session() as db:
        db_agent = await db.get(AgentTable, agent_id)
        if not db_agent:
            raise IntentKitAPIError(
                404, "AgentNotFound", f"Agent '{agent_id}' not found"
            )
        if db_agent.team_id != team_id:
            raise IntentKitAPIError(
                403, "Forbidden", "Agent does not belong to this team"
            )
        return Agent.model_validate(db_agent)
