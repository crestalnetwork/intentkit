import logging

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from intentkit.config.db import get_session
from intentkit.core.agent.queries import get_agent
from intentkit.models.agent.core import AgentVisibility
from intentkit.models.team_feed import (
    TeamActivityFeedTable,
    TeamPostFeedTable,
    TeamSubscription,
    TeamSubscriptionTable,
)
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


async def subscribe_agent(team_id: str, agent_id: str) -> TeamSubscription:
    agent = await get_agent(agent_id)
    if not agent:
        raise IntentKitAPIError(404, "AgentNotFound", f"Agent '{agent_id}' not found")
    if agent.team_id != team_id and agent.visibility != AgentVisibility.PUBLIC:
        raise IntentKitAPIError(
            403, "Forbidden", "Agent is not public and does not belong to this team"
        )

    async with get_session() as session:
        stmt = (
            insert(TeamSubscriptionTable)
            .values(team_id=team_id, agent_id=agent_id)
            .on_conflict_do_nothing()
        )
        await session.execute(stmt)
        await session.commit()

        result = await session.execute(
            select(TeamSubscriptionTable).where(
                TeamSubscriptionTable.team_id == team_id,
                TeamSubscriptionTable.agent_id == agent_id,
            )
        )
        row = result.scalar_one()
        return TeamSubscription.model_validate(row)


async def unsubscribe_agent(team_id: str, agent_id: str) -> None:
    async with get_session() as session:
        await session.execute(
            delete(TeamSubscriptionTable).where(
                TeamSubscriptionTable.team_id == team_id,
                TeamSubscriptionTable.agent_id == agent_id,
            )
        )
        await session.execute(
            delete(TeamActivityFeedTable).where(
                TeamActivityFeedTable.team_id == team_id,
                TeamActivityFeedTable.agent_id == agent_id,
            )
        )
        await session.execute(
            delete(TeamPostFeedTable).where(
                TeamPostFeedTable.team_id == team_id,
                TeamPostFeedTable.agent_id == agent_id,
            )
        )
        await session.commit()


async def get_subscriptions(team_id: str) -> list[TeamSubscription]:
    async with get_session() as session:
        result = await session.execute(
            select(TeamSubscriptionTable)
            .where(TeamSubscriptionTable.team_id == team_id)
            .order_by(TeamSubscriptionTable.subscribed_at.desc())
        )
        rows = result.scalars().all()
        return [TeamSubscription.model_validate(row) for row in rows]


async def auto_subscribe_team(team_id: str, agent_id: str) -> None:
    async with get_session() as session:
        stmt = (
            insert(TeamSubscriptionTable)
            .values(team_id=team_id, agent_id=agent_id)
            .on_conflict_do_nothing()
        )
        await session.execute(stmt)
        await session.commit()
