"""Team utilities for the lead agent."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from intentkit.config.db import get_session
from intentkit.models.agent import Agent
from intentkit.models.agent.db import AgentTable
from intentkit.models.team import TeamMemberTable
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


async def get_team_with_members(team_id: str) -> dict[str, Any]:
    """Return team info + members list (user_id, role, joined_at)."""
    from intentkit.core.team.membership import get_members, get_team

    team = await get_team(team_id)
    if not team:
        raise IntentKitAPIError(404, "TeamNotFound", f"Team '{team_id}' not found")

    members = await get_members(team_id)

    return {
        "id": team.id,
        "name": team.name,
        "avatar": team.avatar,
        "created_at": team.created_at.isoformat() if team.created_at else None,
        "members": [m.model_dump(mode="json") for m in members],
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
