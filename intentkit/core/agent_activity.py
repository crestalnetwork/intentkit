import json
import logging

from sqlalchemy import select

from intentkit.models.agent_activity import (
    AgentActivity,
    AgentActivityCreate,
    AgentActivityTable,
)
from intentkit.models.db import get_session
from intentkit.models.redis import get_redis

logger = logging.getLogger(__name__)


async def create_agent_activity(activity_create: AgentActivityCreate) -> AgentActivity:
    async with get_session() as session:
        db_activity = AgentActivityTable(**activity_create.model_dump())
        session.add(db_activity)
        await session.commit()
        await session.refresh(db_activity)
        return AgentActivity.model_validate(db_activity)


async def get_agent_activity(activity_id: str) -> AgentActivity | None:
    cache_key = f"intentkit:agent_activity:{activity_id}"
    redis_client = None

    try:
        redis_client = get_redis()
    except Exception as exc:  # pragma: no cover
        logger.debug("Redis unavailable for agent activity: %s", exc)

    if redis_client:
        try:
            cached_raw = await redis_client.get(cache_key)
            if cached_raw:
                cached_data = json.loads(cached_raw)
                return AgentActivity.model_validate(cached_data)
        except Exception as exc:  # pragma: no cover
            logger.debug(
                "Failed to read agent activity cache for %s: %s", activity_id, exc
            )

    async with get_session() as session:
        result = await session.execute(
            select(AgentActivityTable).where(AgentActivityTable.id == activity_id)
        )
        db_activity = result.scalar_one_or_none()

        if db_activity is None:
            return None

        activity = AgentActivity.model_validate(db_activity)

    if redis_client:
        try:
            await redis_client.set(
                cache_key,
                json.dumps(activity.model_dump(mode="json")),
                ex=3600,
            )
        except Exception as exc:  # pragma: no cover
            logger.debug(
                "Failed to write agent activity cache for %s: %s", activity_id, exc
            )

    return activity
