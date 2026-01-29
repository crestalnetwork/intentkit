import json

from sqlalchemy import desc, select

from intentkit.config.db import get_session
from intentkit.config.redis import get_redis
from intentkit.models.agent_activity import (
    AgentActivity,
    AgentActivityCreate,
    AgentActivityTable,
)


async def create_agent_activity(activity_create: AgentActivityCreate) -> AgentActivity:
    async with get_session() as session:
        db_activity = AgentActivityTable(**activity_create.model_dump())
        session.add(db_activity)
        await session.commit()
        await session.refresh(db_activity)
        return AgentActivity.model_validate(db_activity)


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
