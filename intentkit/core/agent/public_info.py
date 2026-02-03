from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from intentkit.config.db import get_session
from intentkit.models.agent import AgentPublicInfo, AgentTable
from intentkit.utils.error import IntentKitAPIError

if TYPE_CHECKING:
    from intentkit.models.agent import Agent


async def update_public_info(*, agent_id: str, public_info: AgentPublicInfo) -> Agent:
    """Update agent public info with only the fields that are explicitly provided."""
    from intentkit.models.agent import Agent

    async with get_session() as session:
        result = await session.execute(
            select(AgentTable).where(AgentTable.id == agent_id)
        )
        db_agent = result.scalar_one_or_none()

        if not db_agent:
            raise IntentKitAPIError(404, "NotFound", f"Agent {agent_id} not found")

        update_data = public_info.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            if hasattr(db_agent, key):
                setattr(db_agent, key, value)

        db_agent.public_info_updated_at = func.now()

        await session.commit()
        await session.refresh(db_agent)

        return Agent.model_validate(db_agent)


async def override_public_info(*, agent_id: str, public_info: AgentPublicInfo) -> Agent:
    """Override agent public info with all fields from this instance."""
    from intentkit.models.agent import Agent

    async with get_session() as session:
        result = await session.execute(
            select(AgentTable).where(AgentTable.id == agent_id)
        )
        db_agent = result.scalar_one_or_none()

        if not db_agent:
            raise IntentKitAPIError(404, "NotFound", f"Agent {agent_id} not found")

        update_data = public_info.model_dump()
        for key, value in update_data.items():
            if hasattr(db_agent, key):
                setattr(db_agent, key, value)

        db_agent.public_info_updated_at = func.now()

        await session.commit()
        await session.refresh(db_agent)

        return Agent.model_validate(db_agent)
