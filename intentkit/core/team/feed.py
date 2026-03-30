import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.db import get_session
from intentkit.models.agent.core import AgentVisibility
from intentkit.models.agent.db import AgentTable
from intentkit.models.agent_activity import AgentActivity, AgentActivityTable
from intentkit.models.agent_post import AgentPostBrief, AgentPostTable
from intentkit.models.team_feed import (
    TeamActivityFeedTable,
    TeamPostFeedTable,
    TeamSubscriptionTable,
)
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)

PUBLIC_TEAM_ID = "public"


async def _resolve_target_teams(session: AsyncSession, agent_id: str) -> list[str]:
    """Get all teams that should receive fan-out for an agent's content."""
    result = await session.execute(
        select(TeamSubscriptionTable.team_id).where(
            TeamSubscriptionTable.agent_id == agent_id
        )
    )
    team_ids = list(result.scalars().all())

    # Ensure public agents fan out to the "public" virtual team
    if PUBLIC_TEAM_ID not in team_ids:
        agent_row = await session.get(AgentTable, agent_id)
        if (
            agent_row
            and agent_row.visibility is not None
            and agent_row.visibility >= AgentVisibility.PUBLIC
        ):
            team_ids.append(PUBLIC_TEAM_ID)

    return team_ids


async def fan_out_activity(
    activity_id: str, agent_id: str, created_at: datetime
) -> None:
    async with get_session() as session:
        team_ids = await _resolve_target_teams(session, agent_id)
        if not team_ids:
            return

        values = [
            {
                "team_id": tid,
                "activity_id": activity_id,
                "agent_id": agent_id,
                "created_at": created_at,
            }
            for tid in team_ids
        ]
        stmt = insert(TeamActivityFeedTable).values(values).on_conflict_do_nothing()
        await session.execute(stmt)
        await session.commit()


async def fan_out_post(post_id: str, agent_id: str, created_at: datetime) -> None:
    async with get_session() as session:
        team_ids = await _resolve_target_teams(session, agent_id)
        if not team_ids:
            return

        values = [
            {
                "team_id": tid,
                "post_id": post_id,
                "agent_id": agent_id,
                "created_at": created_at,
            }
            for tid in team_ids
        ]
        stmt = insert(TeamPostFeedTable).values(values).on_conflict_do_nothing()
        await session.execute(stmt)
        await session.commit()


def _parse_cursor(cursor: str) -> tuple[datetime, str]:
    parts = cursor.split("|", 1)
    if len(parts) != 2:
        raise IntentKitAPIError(400, "InvalidCursor", "Malformed cursor")
    try:
        return datetime.fromisoformat(parts[0]), parts[1]
    except ValueError:
        raise IntentKitAPIError(400, "InvalidCursor", "Malformed cursor")


def _build_cursor(created_at: datetime, item_id: str) -> str:
    return f"{created_at.isoformat()}|{item_id}"


async def query_activity_feed(
    team_id: str, limit: int = 20, cursor: str | None = None
) -> tuple[list[AgentActivity], str | None]:
    async with get_session() as session:
        query = select(TeamActivityFeedTable).where(
            TeamActivityFeedTable.team_id == team_id
        )

        if cursor:
            cursor_dt, cursor_id = _parse_cursor(cursor)
            query = query.where(
                (TeamActivityFeedTable.created_at < cursor_dt)
                | (
                    (TeamActivityFeedTable.created_at == cursor_dt)
                    & (TeamActivityFeedTable.activity_id < cursor_id)
                )
            )

        query = query.order_by(
            TeamActivityFeedTable.created_at.desc(),
            TeamActivityFeedTable.activity_id.desc(),
        ).limit(limit + 1)

        result = await session.execute(query)
        feed_rows = result.scalars().all()

        has_more = len(feed_rows) > limit
        feed_rows = feed_rows[:limit]

        if not feed_rows:
            return [], None

        activity_ids = [r.activity_id for r in feed_rows]

        activity_result = await session.execute(
            select(AgentActivityTable).where(AgentActivityTable.id.in_(activity_ids))
        )
        activity_map = {
            row.id: AgentActivity.model_validate(row)
            for row in activity_result.scalars().all()
        }

        items = [activity_map[aid] for aid in activity_ids if aid in activity_map]

        next_cursor = None
        if has_more and feed_rows:
            last = feed_rows[-1]
            next_cursor = _build_cursor(last.created_at, last.activity_id)

        return items, next_cursor


async def query_post_feed(
    team_id: str, limit: int = 20, cursor: str | None = None
) -> tuple[list[AgentPostBrief], str | None]:
    async with get_session() as session:
        query = select(TeamPostFeedTable).where(TeamPostFeedTable.team_id == team_id)

        if cursor:
            cursor_dt, cursor_id = _parse_cursor(cursor)
            query = query.where(
                (TeamPostFeedTable.created_at < cursor_dt)
                | (
                    (TeamPostFeedTable.created_at == cursor_dt)
                    & (TeamPostFeedTable.post_id < cursor_id)
                )
            )

        query = query.order_by(
            TeamPostFeedTable.created_at.desc(),
            TeamPostFeedTable.post_id.desc(),
        ).limit(limit + 1)

        result = await session.execute(query)
        feed_rows = result.scalars().all()

        has_more = len(feed_rows) > limit
        feed_rows = feed_rows[:limit]

        if not feed_rows:
            return [], None

        post_ids = [r.post_id for r in feed_rows]

        post_result = await session.execute(
            select(AgentPostTable).where(AgentPostTable.id.in_(post_ids))
        )
        post_map = {
            row.id: AgentPostBrief.from_table(row)
            for row in post_result.scalars().all()
        }

        items = [post_map[pid] for pid in post_ids if pid in post_map]

        next_cursor = None
        if has_more and feed_rows:
            last = feed_rows[-1]
            next_cursor = _build_cursor(last.created_at, last.post_id)

        return items, next_cursor
