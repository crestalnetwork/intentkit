from __future__ import annotations

import logging
import warnings
from datetime import datetime
from typing import Annotated, Any, ClassVar

from pydantic import ConfigDict
from pydantic import Field as PydanticField
from sqlalchemy import func, select

from intentkit.config.db import get_session
from intentkit.models.agent.db import AgentTable
from intentkit.models.agent.public_info import AgentPublicInfo
from intentkit.models.agent.user_input import AgentCreate
from intentkit.models.credit import CreditAccount
from intentkit.models.llm import LLMModelInfo

logger = logging.getLogger(__name__)


class Agent(AgentCreate, AgentPublicInfo):
    """Agent model."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    version: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Version hash of the agent",
        ),
    ] = None
    statistics: Annotated[
        dict[str, Any] | None,
        PydanticField(
            default=None,
            description="Statistics of the agent, update every 1 hour for query",
        ),
    ] = None
    assets: Annotated[
        dict[str, Any] | None,
        PydanticField(
            default=None,
            description="Assets of the agent, update every 1 hour for query",
        ),
    ] = None
    account_snapshot: Annotated[
        CreditAccount | None,
        PydanticField(
            default=None,
            description="Account snapshot of the agent, update every 1 hour for query",
        ),
    ] = None
    extra: Annotated[
        dict[str, Any] | None,
        PydanticField(
            default=None,
            description="Other helper data fields for query, come from agent and agent data",
        ),
    ] = None
    public_info_updated_at: Annotated[
        datetime | None,
        PydanticField(
            default=None,
            description="Timestamp when the agent public info was last updated",
        ),
    ] = None
    # auto timestamp
    created_at: Annotated[
        datetime,
        PydanticField(description="Timestamp when the agent was created"),
    ]
    updated_at: Annotated[
        datetime,
        PydanticField(description="Timestamp when the agent was last updated"),
    ]

    async def is_model_support_image(self) -> bool:
        try:
            model = await LLMModelInfo.get(self.model)
            return model.supports_image_input
        except Exception:
            return False

    @staticmethod
    async def count() -> int:
        async with get_session() as db:
            result = await db.scalar(select(func.count(AgentTable.id)))
            return result or 0

    @classmethod
    async def get(cls, agent_id: str) -> Agent | None:
        """Get agent by ID from database.

        .. deprecated::
            Use :func:`intentkit.core.agent.get_agent` instead.
            This method will be removed in a future version.
        """
        warnings.warn(
            "Agent.get() is deprecated, use intentkit.core.agent.get_agent() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        async with get_session() as db:
            item = await db.scalar(select(AgentTable).where(AgentTable.id == agent_id))
            if item is None:
                return None
            return cls.model_validate(item)
