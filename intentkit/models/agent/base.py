from __future__ import annotations

import hashlib
import json
import logging
from decimal import Decimal
from enum import IntEnum
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField
from sqlalchemy import func, select

from intentkit.config.db import get_session
from intentkit.models.agent.db import AgentTable
from intentkit.models.agent.example import AgentExample
from intentkit.utils.error import IntentKitAPIError

if TYPE_CHECKING:
    from intentkit.models.agent.core import Agent

logger = logging.getLogger(__name__)


class AgentVisibility(IntEnum):
    """Agent visibility levels with hierarchical ordering.

    Higher values indicate broader visibility:
    - PRIVATE (0): Only visible to owner
    - TEAM (10): Visible to team members
    - PUBLIC (20): Visible to everyone
    """

    PRIVATE = 0
    TEAM = 10
    PUBLIC = 20


class AgentCore(BaseModel):
    """Agent core model."""

    name: Annotated[
        str | None,
        PydanticField(
            default=None,
            title="Name",
            description="Display name of the agent",
            max_length=50,
        ),
    ]
    picture: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Avatar of the agent",
        ),
    ]
    purpose: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Purpose or role of the agent",
            max_length=20000,
        ),
    ]
    personality: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Personality traits of the agent",
            max_length=20000,
        ),
    ]
    principles: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Principles or values of the agent",
            max_length=20000,
        ),
    ]
    # AI part
    model: Annotated[
        str,
        PydanticField(
            default="gpt-5-mini",
            description="LLM of the agent",
        ),
    ]
    prompt: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Base system prompt that defines the agent's behavior and capabilities",
            max_length=20000,
        ),
    ]
    prompt_append: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Additional system prompt that has higher priority than the base prompt",
            max_length=20000,
        ),
    ]
    temperature: Annotated[
        float | None,
        PydanticField(
            default=0.7,
            description="The randomness of the generated results is such that the higher the number, the more creative the results will be. However, this also makes them wilder and increases the likelihood of errors. For creative tasks, you can adjust it to above 1, but for rigorous tasks, such as quantitative trading, it's advisable to set it lower, around 0.2. (0.0~2.0)",
            ge=0.0,
            le=2.0,
        ),
    ]
    frequency_penalty: Annotated[
        float | None,
        PydanticField(
            default=0.0,
            description="The frequency penalty is a measure of how much the AI is allowed to repeat itself. A lower value means the AI is more likely to repeat previous responses, while a higher value means the AI is more likely to generate new content. For creative tasks, you can adjust it to 1 or a bit higher. (-2.0~2.0)",
            ge=-2.0,
            le=2.0,
        ),
    ]
    presence_penalty: Annotated[
        float | None,
        PydanticField(
            default=0.0,
            description="The presence penalty is a measure of how much the AI is allowed to deviate from the topic. A higher value means the AI is more likely to deviate from the topic, while a lower value means the AI is more likely to follow the topic. For creative tasks, you can adjust it to 1 or a bit higher. (-2.0~2.0)",
            ge=-2.0,
            le=2.0,
        ),
    ]
    short_term_memory_strategy: Annotated[
        Literal["trim", "summarize"] | None,
        PydanticField(
            default="trim",
            description="Strategy for managing short-term memory when context limit is reached. 'trim' removes oldest messages, 'summarize' creates summaries.",
        ),
    ]
    wallet_provider: Annotated[
        Literal["cdp", "native", "readonly", "safe", "privy", "none"] | None,
        PydanticField(
            default=None,
            description="Provider of the agent's wallet",
        ),
    ]
    network_id: Annotated[
        Literal[
            "base-mainnet",
            "ethereum-mainnet",
            "polygon-mainnet",
            "arbitrum-mainnet",
            "optimism-mainnet",
            "bnb-mainnet",
            "solana",
            "base-sepolia",
        ]
        | None,
        PydanticField(
            default="base-mainnet",
            description="Network identifier",
        ),
    ]
    skills: Annotated[
        dict[str, Any] | None,
        PydanticField(
            default=None,
            description="Dict of skills and their corresponding configurations",
        ),
    ]

    def hash(self) -> str:
        """
        Generate a fixed-length hash based on the agent's content.

        The hash remains unchanged if the content is the same and changes if the content changes.
        This method serializes only AgentCore fields to JSON and generates a SHA-256 hash.
        When called from subclasses, it will only use AgentCore fields, not subclass fields.

        Returns:
            str: A 64-character hexadecimal hash string
        """
        # Create a dictionary with only AgentCore fields for hashing
        hash_data = {}

        # Get only AgentCore field values, excluding None values for consistency
        for field_name in AgentCore.model_fields:
            value = getattr(self, field_name)
            if value is not None:
                hash_data[field_name] = value

        # Convert to JSON string with sorted keys for consistent ordering
        json_str = json.dumps(hash_data, sort_keys=True, default=str, ensure_ascii=True)

        # Generate SHA-256 hash
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()


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
        from intentkit.models.agent.core import Agent

        async with get_session() as session:
            # Get the agent from database
            result = await session.execute(
                select(AgentTable).where(AgentTable.id == agent_id)
            )
            db_agent = result.scalar_one_or_none()

            if not db_agent:
                raise IntentKitAPIError(404, "NotFound", f"Agent {agent_id} not found")

            # Get only the fields that are explicitly provided (exclude_unset=True)
            update_data = self.model_dump(exclude_unset=True)

            # Apply the updates to the database agent
            for key, value in update_data.items():
                if hasattr(db_agent, key):
                    setattr(db_agent, key, value)

            # Update public_info_updated_at timestamp
            db_agent.public_info_updated_at = func.now()

            # Commit changes
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
        from intentkit.models.agent.core import Agent

        async with get_session() as session:
            # Get the agent from database
            result = await session.execute(
                select(AgentTable).where(AgentTable.id == agent_id)
            )
            db_agent = result.scalar_one_or_none()

            if not db_agent:
                raise IntentKitAPIError(404, "NotFound", f"Agent {agent_id} not found")

            # Update public info fields
            update_data = self.model_dump()
            for key, value in update_data.items():
                if hasattr(db_agent, key):
                    setattr(db_agent, key, value)

            # Update public_info_updated_at timestamp
            db_agent.public_info_updated_at = func.now()

            # Commit changes
            await session.commit()
            await session.refresh(db_agent)

            return Agent.model_validate(db_agent)
