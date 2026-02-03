from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField
from sqlalchemy import func, select

from intentkit.config.db import get_session
from intentkit.models.agent.db import AgentTable
from intentkit.models.agent.example import AgentExample
from intentkit.utils.error import IntentKitAPIError

if TYPE_CHECKING:
    from intentkit.models.agent.agent import Agent


class AgentPublicInfo(BaseModel):
    """Public information of the agent."""

    model_config = ConfigDict(
        title="AgentPublicInfo",
        from_attributes=True,
    )

    x402_price: Annotated[
        float | None,
        PydanticField(
            default=0.01,
            description="Price($) of the x402 request",
            ge=0.01,
            le=1.0,
            json_schema_extra={
                "x-placeholder": "USDC price per request",
                "x-step": 0.01,
            },
        ),
    ]
    description: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Description of the agent, for public view, not contained in prompt",
            json_schema_extra={
                "x-placeholder": "Introduce your agent",
            },
        ),
    ]
    external_website: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Link of external website of the agent, if you have one",
            json_schema_extra={
                "x-placeholder": "Enter agent external website url",
                "format": "uri",
            },
        ),
    ]
    ticker: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Ticker symbol of the agent",
            max_length=10,
            min_length=1,
            json_schema_extra={
                "x-placeholder": "If one day, your agent has it's own token, what will it be?",
            },
        ),
    ]
    token_address: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Token address of the agent",
            max_length=66,
            json_schema_extra={
                "x-placeholder": "The contract address of the agent token",
            },
        ),
    ]
    token_pool: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Pool of the agent token",
            max_length=66,
            json_schema_extra={
                "x-placeholder": "The contract address of the agent token pool",
            },
        ),
    ]
    fee_percentage: Annotated[
        Decimal | None,
        PydanticField(
            default=None,
            description="Fee percentage of the agent",
            ge=Decimal("0.0"),
            json_schema_extra={
                "x-placeholder": "Agent will charge service fee according to this ratio.",
            },
        ),
    ]
    example_intro: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Introduction of the example",
            max_length=2000,
            json_schema_extra={
                "x-placeholder": "Add a short introduction in new chat",
            },
        ),
    ]
    examples: Annotated[
        list[AgentExample] | None,
        PydanticField(
            default=None,
            description="List of example prompts for the agent",
            max_length=6,
            json_schema_extra={
                "x-inline": True,
            },
        ),
    ]
    public_extra: Annotated[
        dict[str, Any] | None,
        PydanticField(
            default=None,
            description="Public extra data of the agent",
        ),
    ]

    async def update(self, agent_id: str) -> "Agent":
        """Update agent public info with only the fields that are explicitly provided.

        This method only updates fields that are explicitly set in this instance,
        leaving other fields unchanged. This is more efficient than override as it
        reduces context usage and minimizes the risk of accidentally changing fields.

        Args:
            agent_id: The ID of the agent to update

        Returns:
            The updated Agent instance
        """
        from intentkit.models.agent.agent import Agent

        async with get_session() as session:
            result = await session.execute(
                select(AgentTable).where(AgentTable.id == agent_id)
            )
            db_agent = result.scalar_one_or_none()

            if not db_agent:
                raise IntentKitAPIError(404, "NotFound", f"Agent {agent_id} not found")

            update_data = self.model_dump(exclude_unset=True)

            for key, value in update_data.items():
                if hasattr(db_agent, key):
                    setattr(db_agent, key, value)

            db_agent.public_info_updated_at = func.now()

            await session.commit()
            await session.refresh(db_agent)

            return Agent.model_validate(db_agent)

    async def override(self, agent_id: str) -> "Agent":
        """Override agent public info with all fields from this instance.

        Args:
            agent_id: The ID of the agent to override

        Returns:
            The updated Agent instance
        """
        from intentkit.models.agent.agent import Agent

        async with get_session() as session:
            result = await session.execute(
                select(AgentTable).where(AgentTable.id == agent_id)
            )
            db_agent = result.scalar_one_or_none()

            if not db_agent:
                raise IntentKitAPIError(404, "NotFound", f"Agent {agent_id} not found")

            update_data = self.model_dump()
            for key, value in update_data.items():
                if hasattr(db_agent, key):
                    setattr(db_agent, key, value)

            db_agent.public_info_updated_at = func.now()

            await session.commit()
            await session.refresh(db_agent)

            return Agent.model_validate(db_agent)
