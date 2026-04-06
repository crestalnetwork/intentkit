import asyncio
import json
import logging

from sqlalchemy import desc, select

from intentkit.config.db import get_session
from intentkit.config.redis import get_redis
from intentkit.models.agent_activity import (
    AgentActivity,
    AgentActivityCreate,
    AgentActivityTable,
)

logger = logging.getLogger(__name__)


async def create_agent_activity(activity_create: AgentActivityCreate) -> AgentActivity:
    async with get_session() as session:
        db_activity = AgentActivityTable(**activity_create.model_dump())
        session.add(db_activity)
        await session.commit()
        await session.refresh(db_activity)
        activity = AgentActivity.model_validate(db_activity)

    team_ids: list[str] = []
    try:
        from intentkit.core.team.feed import fan_out_activity

        team_ids = await fan_out_activity(
            activity.id, activity.agent_id, activity.created_at
        )
    except Exception:
        logger.exception("Failed to fan out activity %s", activity.id)

    # Push to each team's channel in background (don't block the caller)
    if team_ids:
        asyncio.create_task(_push_activity_to_teams(activity, team_ids))

    return activity


async def _push_activity_to_teams(activity: AgentActivity, team_ids: list[str]) -> None:
    """Push activity to all target teams' channels concurrently."""
    try:
        from intentkit.core.team.push import push_to_team

        push_text = _format_activity_push(activity)
        targets = [tid for tid in team_ids if tid != "public"]
        if not targets:
            return

        results = await asyncio.gather(
            *(push_to_team(tid, push_text) for tid in targets),
            return_exceptions=True,
        )
        for tid, result in zip(targets, results):
            if isinstance(result, Exception):
                logger.exception("Failed to push activity to team %s: %s", tid, result)
    except Exception:
        logger.exception("Failed to push activity %s", activity.id)


def _format_activity_push(activity: AgentActivity) -> str:
    """Format an activity as a push notification message."""
    name = activity.agent_name or activity.agent_id
    text = f"[{name}] {activity.text}"
    if activity.link:
        text += f"\n{activity.link}"
    return text


async def get_agent_activity(activity_id: str) -> AgentActivity | None:
    cache_key = f"intentkit:agent_activity:{activity_id}"
    redis_client = get_redis()

    cached_raw = await redis_client.get(cache_key)
    if cached_raw:
        cached_data = json.loads(cached_raw)
        return AgentActivity.model_validate(cached_data)

    async with get_session() as session:
        result = await session.execute(
            select(AgentActivityTable).where(AgentActivityTable.id == activity_id)
        )
        db_activity = result.scalar_one_or_none()

        if db_activity is None:
            return None

        activity = AgentActivity.model_validate(db_activity)

    await redis_client.set(
        cache_key,
        json.dumps(activity.model_dump(mode="json")),
        ex=3600,
    )

    return activity


async def get_agent_activities(agent_id: str, limit: int = 10) -> list[AgentActivity]:
    """Get recent activities for a specific agent.

    Args:
        agent_id: The ID of the agent.
        limit: Maximum number of activities to retrieve (default: 10).

    Returns:
        List of AgentActivity objects, ordered by created_at descending.
    """
    async with get_session() as session:
        result = await session.execute(
            select(AgentActivityTable)
            .where(AgentActivityTable.agent_id == agent_id)
            .order_by(desc(AgentActivityTable.created_at))
            .limit(limit)
        )
        db_activities = result.scalars().all()
        return [AgentActivity.model_validate(activity) for activity in db_activities]
