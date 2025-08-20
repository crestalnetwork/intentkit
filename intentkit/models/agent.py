import json
import logging
import re
import textwrap
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any, Dict, List, Literal, Optional

import jsonref
import yaml
from cron_validator import CronValidator
from epyxid import XID
from fastapi import HTTPException
from intentkit.models.agent_data import AgentData
from intentkit.models.base import Base
from intentkit.models.db import get_session
from intentkit.models.llm import LLMModelInfo, LLMModelInfoTable, LLMProvider
from intentkit.models.skill import SkillTable
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pydantic import Field as PydanticField
from pydantic.json_schema import SkipJsonSchema
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Numeric,
    String,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AgentAutonomous(BaseModel):
    """Autonomous agent configuration."""

    id: Annotated[
        str,
        PydanticField(
            description="Unique identifier for the autonomous configuration",
            default_factory=lambda: str(XID()),
            min_length=1,
            max_length=20,
            pattern=r"^[a-z0-9-]+$",
            json_schema_extra={
                "x-group": "autonomous",
            },
        ),
    ]
    name: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Display name of the autonomous configuration",
            max_length=50,
            json_schema_extra={
                "x-group": "autonomous",
            },
        ),
    ]
    description: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Description of the autonomous configuration",
            max_length=200,
            json_schema_extra={
                "x-group": "autonomous",
            },
        ),
    ]
    minutes: Annotated[
        Optional[int],
        PydanticField(
            default=None,
            description="Interval in minutes between operations, mutually exclusive with cron",
            json_schema_extra={
                "x-group": "autonomous",
            },
        ),
    ]
    cron: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Cron expression for scheduling operations, mutually exclusive with minutes",
            json_schema_extra={
                "x-group": "autonomous",
            },
        ),
    ]
    prompt: Annotated[
        str,
        PydanticField(
            description="Special prompt used during autonomous operation",
            max_length=20000,
            json_schema_extra={
                "x-group": "autonomous",
            },
        ),
    ]
    enabled: Annotated[
        Optional[bool],
        PydanticField(
            default=False,
            description="Whether the autonomous configuration is enabled",
            json_schema_extra={
                "x-group": "autonomous",
            },
        ),
    ]

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not v:
            raise ValueError("id cannot be empty")
        if len(v.encode()) > 20:
            raise ValueError("id must be at most 20 bytes")
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError(
                "id must contain only lowercase letters, numbers, and dashes"
            )
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v.encode()) > 50:
            raise ValueError("name must be at most 50 bytes")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v.encode()) > 200:
            raise ValueError("description must be at most 200 bytes")
        return v

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v.encode()) > 20000:
            raise ValueError("prompt must be at most 20000 bytes")
        return v

    @model_validator(mode="after")
    def validate_schedule(self) -> "AgentAutonomous":
        # This validator is kept for backward compatibility
        # The actual validation now happens in AgentUpdate.validate_autonomous_schedule
        return self


class AgentExample(BaseModel):
    """Agent example configuration."""

    name: Annotated[
        str,
        PydanticField(
            description="Name of the example",
            max_length=50,
            json_schema_extra={
                "x-group": "examples",
            },
        ),
    ]
    description: Annotated[
        str,
        PydanticField(
            description="Description of the example",
            max_length=200,
            json_schema_extra={
                "x-group": "examples",
            },
        ),
    ]
    prompt: Annotated[
        str,
        PydanticField(
            description="Example prompt",
            max_length=2000,
            json_schema_extra={
                "x-group": "examples",
            },
        ),
    ]


class AgentTable(Base):
    """Agent table db model."""

    __tablename__ = "agents"

    id = Column(
        String,
        primary_key=True,
        comment="Unique identifier for the agent. Must be URL-safe, containing only lowercase letters, numbers, and hyphens",
    )
    name = Column(
        String,
        nullable=True,
        comment="Display name of the agent",
    )
    slug = Column(
        String,
        nullable=True,
        comment="Slug of the agent, used for URL generation",
    )
    description = Column(
        String,
        nullable=True,
        comment="Description of the agent, for public view, not contained in prompt",
    )
    external_website = Column(
        String,
        nullable=True,
        comment="Link of external website of the agent, if you have one",
    )
    picture = Column(
        String,
        nullable=True,
        comment="Picture of the agent",
    )
    ticker = Column(
        String,
        nullable=True,
        comment="Ticker symbol of the agent",
    )
    token_address = Column(
        String,
        nullable=True,
        comment="Token address of the agent",
    )
    token_pool = Column(
        String,
        nullable=True,
        comment="Pool of the agent token",
    )
    mode = Column(
        String,
        nullable=True,
        comment="Mode of the agent, public or private",
    )
    fee_percentage = Column(
        Numeric(22, 4),
        nullable=True,
        comment="Fee percentage of the agent",
    )
    purpose = Column(
        String,
        nullable=True,
        comment="Purpose or role of the agent",
    )
    personality = Column(
        String,
        nullable=True,
        comment="Personality traits of the agent",
    )
    principles = Column(
        String,
        nullable=True,
        comment="Principles or values of the agent",
    )
    owner = Column(
        String,
        nullable=True,
        comment="Owner identifier of the agent, used for access control",
    )
    upstream_id = Column(
        String,
        index=True,
        nullable=True,
        comment="Upstream reference ID for idempotent operations",
    )
    upstream_extra = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Additional data store for upstream use",
    )
    wallet_provider = Column(
        String,
        nullable=True,
        comment="Provider of the agent's wallet",
    )
    readonly_wallet_address = Column(
        String,
        nullable=True,
        comment="Readonly wallet address of the agent",
    )
    network_id = Column(
        String,
        nullable=True,
        default="base-mainnet",
        comment="Network identifier",
    )
    # AI part
    model = Column(
        String,
        nullable=True,
        default="gpt-5-mini",
        comment="AI model identifier to be used by this agent for processing requests. Available models: gpt-4o, gpt-4o-mini, deepseek-chat, deepseek-reasoner, grok-2, eternalai",
    )
    prompt = Column(
        String,
        nullable=True,
        comment="Base system prompt that defines the agent's behavior and capabilities",
    )
    prompt_append = Column(
        String,
        nullable=True,
        comment="Additional system prompt that has higher priority than the base prompt",
    )
    temperature = Column(
        Float,
        nullable=True,
        default=0.7,
        comment="Controls response randomness (0.0~2.0). Higher values increase creativity but may reduce accuracy. For rigorous tasks, use lower values.",
    )
    frequency_penalty = Column(
        Float,
        nullable=True,
        default=0.0,
        comment="Controls repetition in responses (-2.0~2.0). Higher values reduce repetition, lower values allow more repetition.",
    )
    presence_penalty = Column(
        Float,
        nullable=True,
        default=0.0,
        comment="Controls topic adherence (-2.0~2.0). Higher values allow more topic deviation, lower values enforce stricter topic adherence.",
    )
    short_term_memory_strategy = Column(
        String,
        nullable=True,
        default="trim",
        comment="Strategy for managing short-term memory when context limit is reached. 'trim' removes oldest messages, 'summarize' creates summaries.",
    )
    # autonomous mode
    autonomous = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Autonomous agent configurations",
    )
    # agent examples
    example_intro = Column(
        String,
        nullable=True,
        comment="Introduction for example interactions",
    )
    examples = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="List of example interactions for the agent",
    )
    # skills
    skills = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Dict of skills and their corresponding configurations",
    )

    cdp_network_id = Column(
        String,
        nullable=True,
        default="base-mainnet",
        comment="Network identifier for CDP integration",
    )
    # if telegram_entrypoint_enabled, the telegram_entrypoint_enabled will be enabled, telegram_config will be checked
    telegram_entrypoint_enabled = Column(
        Boolean,
        nullable=True,
        default=False,
        comment="Whether the agent can receive events from Telegram",
    )
    telegram_entrypoint_prompt = Column(
        String,
        nullable=True,
        comment="Extra prompt for telegram entrypoint",
    )
    telegram_config = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Telegram integration configuration settings",
    )
    xmtp_entrypoint_prompt = Column(
        String,
        nullable=True,
        comment="Extra prompt for xmtp entrypoint",
    )
    # auto timestamp
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when the agent was created",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Timestamp when the agent was last updated",
    )


class AgentUpdate(BaseModel):
    """Agent update model."""

    model_config = ConfigDict(
        title="Agent",
        from_attributes=True,
        json_schema_extra={
            "required": ["name", "purpose", "personality", "principles"],
        },
    )

    name: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            title="Name",
            description="Display name of the agent",
            max_length=50,
            json_schema_extra={
                "x-group": "basic",
                "x-placeholder": "Name your agent",
            },
        ),
    ]
    slug: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Slug of the agent, used for URL generation",
            max_length=30,
            min_length=2,
            json_schema_extra={
                "x-group": "internal",
                "readOnly": True,
            },
        ),
    ]
    description: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Description of the agent, for public view, not contained in prompt",
            json_schema_extra={
                "x-group": "basic",
                "x-placeholder": "Introduce your agent",
            },
        ),
    ]
    external_website: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Link of external website of the agent, if you have one",
            json_schema_extra={
                "x-group": "basic",
                "x-placeholder": "Enter agent external website url",
                "format": "uri",
            },
        ),
    ]
    picture: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Picture of the agent",
            json_schema_extra={
                "x-group": "experimental",
                "x-placeholder": "Upload a picture of your agent",
            },
        ),
    ]
    ticker: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Ticker symbol of the agent",
            max_length=10,
            min_length=1,
            json_schema_extra={
                "x-group": "basic",
                "x-placeholder": "If one day, your agent has it's own token, what will it be?",
            },
        ),
    ]
    token_address: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Token address of the agent",
            max_length=42,
            json_schema_extra={
                "x-group": "internal",
                "readOnly": True,
            },
        ),
    ]
    token_pool: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Pool of the agent token",
            max_length=42,
            json_schema_extra={
                "x-group": "internal",
                "readOnly": True,
            },
        ),
    ]
    mode: Annotated[
        Optional[Literal["public", "private"]],
        PydanticField(
            default=None,
            description="Mode of the agent, public or private",
            json_schema_extra={
                "x-group": "basic",
            },
        ),
    ]
    fee_percentage: Annotated[
        Optional[Decimal],
        PydanticField(
            default=None,
            description="Fee percentage of the agent",
            ge=Decimal("0.0"),
            json_schema_extra={
                "x-group": "basic",
            },
        ),
    ]
    purpose: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Purpose or role of the agent",
            max_length=20000,
            json_schema_extra={
                "x-group": "basic",
                "x-placeholder": "Enter agent purpose, it will be a part of the system prompt",
                "pattern": "^(([^#].*)|#[^# ].*|#{3,}[ ].*|$)(\n(([^#].*)|#[^# ].*|#{3,}[ ].*|$))*$",
                "errorMessage": {
                    "pattern": "Level 1 and 2 headings (# and ##) are not allowed. Please use level 3+ headings (###, ####, etc.) instead."
                },
            },
        ),
    ]
    personality: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Personality traits of the agent",
            max_length=20000,
            json_schema_extra={
                "x-group": "basic",
                "x-placeholder": "Enter agent personality, it will be a part of the system prompt",
                "pattern": "^(([^#].*)|#[^# ].*|#{3,}[ ].*|$)(\n(([^#].*)|#[^# ].*|#{3,}[ ].*|$))*$",
                "errorMessage": {
                    "pattern": "Level 1 and 2 headings (# and ##) are not allowed. Please use level 3+ headings (###, ####, etc.) instead."
                },
            },
        ),
    ]
    principles: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Principles or values of the agent",
            max_length=20000,
            json_schema_extra={
                "x-group": "basic",
                "x-placeholder": "Enter agent principles, it will be a part of the system prompt",
                "pattern": "^(([^#].*)|#[^# ].*|#{3,}[ ].*|$)(\n(([^#].*)|#[^# ].*|#{3,}[ ].*|$))*$",
                "errorMessage": {
                    "pattern": "Level 1 and 2 headings (# and ##) are not allowed. Please use level 3+ headings (###, ####, etc.) instead."
                },
            },
        ),
    ]
    owner: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Owner identifier of the agent, used for access control",
            max_length=50,
            json_schema_extra={
                "x-group": "internal",
            },
        ),
    ]
    upstream_id: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="External reference ID for idempotent operations",
            max_length=100,
            json_schema_extra={
                "x-group": "internal",
            },
        ),
    ]
    upstream_extra: Annotated[
        Optional[Dict[str, Any]],
        PydanticField(
            default=None,
            description="Additional data store for upstream use",
            json_schema_extra={
                "x-group": "internal",
            },
        ),
    ]
    # AI part
    model: Annotated[
        str,
        PydanticField(
            default="gpt-5-mini",
            description="AI model identifier to be used by this agent for processing requests.",
            json_schema_extra={
                "x-group": "ai",
            },
        ),
    ]
    prompt: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Base system prompt that defines the agent's behavior and capabilities",
            max_length=20000,
            json_schema_extra={
                "x-group": "ai",
                "pattern": "^(([^#].*)|#[^# ].*|#{3,}[ ].*|$)(\n(([^#].*)|#[^# ].*|#{3,}[ ].*|$))*$",
                "errorMessage": {
                    "pattern": "Level 1 and 2 headings (# and ##) are not allowed. Please use level 3+ headings (###, ####, etc.) instead."
                },
            },
        ),
    ]
    prompt_append: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Additional system prompt that has higher priority than the base prompt",
            max_length=20000,
            json_schema_extra={
                "x-group": "ai",
                "pattern": "^(([^#].*)|#[^# ].*|#{3,}[ ].*|$)(\n(([^#].*)|#[^# ].*|#{3,}[ ].*|$))*$",
                "errorMessage": {
                    "pattern": "Level 1 and 2 headings (# and ##) are not allowed. Please use level 3+ headings (###, ####, etc.) instead."
                },
            },
        ),
    ]
    temperature: Annotated[
        Optional[float],
        PydanticField(
            default=0.7,
            description="The randomness of the generated results is such that the higher the number, the more creative the results will be. However, this also makes them wilder and increases the likelihood of errors. For creative tasks, you can adjust it to above 1, but for rigorous tasks, such as quantitative trading, it's advisable to set it lower, around 0.2. (0.0~2.0)",
            ge=0.0,
            le=2.0,
            json_schema_extra={
                "x-group": "ai",
            },
        ),
    ]
    frequency_penalty: Annotated[
        Optional[float],
        PydanticField(
            default=0.0,
            description="The frequency penalty is a measure of how much the AI is allowed to repeat itself. A lower value means the AI is more likely to repeat previous responses, while a higher value means the AI is more likely to generate new content. For creative tasks, you can adjust it to 1 or a bit higher. (-2.0~2.0)",
            ge=-2.0,
            le=2.0,
            json_schema_extra={
                "x-group": "ai",
            },
        ),
    ]
    presence_penalty: Annotated[
        Optional[float],
        PydanticField(
            default=0.0,
            description="The presence penalty is a measure of how much the AI is allowed to deviate from the topic. A higher value means the AI is more likely to deviate from the topic, while a lower value means the AI is more likely to follow the topic. For creative tasks, you can adjust it to 1 or a bit higher. (-2.0~2.0)",
            ge=-2.0,
            le=2.0,
            json_schema_extra={
                "x-group": "ai",
            },
        ),
    ]
    short_term_memory_strategy: Annotated[
        Optional[Literal["trim", "summarize"]],
        PydanticField(
            default="trim",
            description="Strategy for managing short-term memory when context limit is reached. 'trim' removes oldest messages, 'summarize' creates summaries.",
            json_schema_extra={
                "x-group": "ai",
            },
        ),
    ]
    # autonomous mode
    autonomous: Annotated[
        Optional[List[AgentAutonomous]],
        PydanticField(
            default=None,
            description=(
                "Autonomous agent configurations.\n"
                "autonomous:\n"
                "  - id: a\n"
                "    name: TestA\n"
                "    minutes: 1\n"
                "    prompt: |-\n"
                "      Say hello [sequence], use number for sequence.\n"
                "  - id: b\n"
                "    name: TestB\n"
                '    cron: "0/3 * * * *"\n'
                "    prompt: |-\n"
                "      Say hi [sequence], use number for sequence.\n"
            ),
            json_schema_extra={
                "x-group": "autonomous",
                "x-inline": True,
            },
        ),
    ]
    example_intro: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Introduction of the example",
            max_length=2000,
            json_schema_extra={
                "x-group": "examples",
            },
        ),
    ]
    examples: Annotated[
        Optional[List[AgentExample]],
        PydanticField(
            default=None,
            description="List of example prompts for the agent",
            max_length=6,
            json_schema_extra={
                "x-group": "examples",
                "x-inline": True,
            },
        ),
    ]
    # skills
    skills: Annotated[
        Optional[Dict[str, Any]],
        PydanticField(
            default=None,
            description="Dict of skills and their corresponding configurations",
            json_schema_extra={
                "x-group": "skills",
                "x-inline": True,
            },
        ),
    ]
    wallet_provider: Annotated[
        Optional[Literal["cdp", "readonly"]],
        PydanticField(
            default="cdp",
            description="Provider of the agent's wallet",
            json_schema_extra={
                "x-group": "onchain",
            },
        ),
    ]
    readonly_wallet_address: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Address of the agent's wallet, only used when wallet_provider is readonly. Agent will not be able to sign transactions.",
        ),
    ]
    network_id: Annotated[
        Optional[
            Literal[
                "ethereum-mainnet",
                "ethereum-sepolia",
                "polygon-mainnet",
                "polygon-mumbai",
                "base-mainnet",
                "base-sepolia",
                "arbitrum-mainnet",
                "arbitrum-sepolia",
                "optimism-mainnet",
                "optimism-sepolia",
                "solana",
            ]
        ],
        PydanticField(
            default="base-mainnet",
            description="Network identifier",
            json_schema_extra={
                "x-group": "onchain",
            },
        ),
    ]
    cdp_network_id: Annotated[
        Optional[
            Literal[
                "ethereum-mainnet",
                "ethereum-sepolia",
                "polygon-mainnet",
                "polygon-mumbai",
                "base-mainnet",
                "base-sepolia",
                "arbitrum-mainnet",
                "arbitrum-sepolia",
                "optimism-mainnet",
                "optimism-sepolia",
            ]
        ],
        PydanticField(
            default="base-mainnet",
            description="Network identifier for CDP integration",
            json_schema_extra={
                "x-group": "deprecated",
            },
        ),
    ]
    # if telegram_entrypoint_enabled, the telegram_entrypoint_enabled will be enabled, telegram_config will be checked
    telegram_entrypoint_enabled: Annotated[
        Optional[bool],
        PydanticField(
            default=False,
            description="Whether the agent can play telegram bot",
            json_schema_extra={
                "x-group": "entrypoint",
            },
        ),
    ]
    telegram_entrypoint_prompt: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Extra prompt for telegram entrypoint",
            max_length=10000,
            json_schema_extra={
                "x-group": "entrypoint",
            },
        ),
    ]
    telegram_config: Annotated[
        Optional[dict],
        PydanticField(
            default=None,
            description="Telegram integration configuration settings",
            json_schema_extra={
                "x-group": "entrypoint",
            },
        ),
    ]
    xmtp_entrypoint_prompt: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Extra prompt for xmtp entrypoint, xmtp support is in beta",
            max_length=10000,
            json_schema_extra={
                "x-group": "entrypoint",
            },
        ),
    ]

    @field_validator("purpose", "personality", "principles", "prompt", "prompt_append")
    @classmethod
    def validate_no_level1_level2_headings(cls, v: Optional[str]) -> Optional[str]:
        """Validate that the text doesn't contain level 1 or level 2 headings."""
        if v is None:
            return v

        import re

        # Check if any line starts with # or ## followed by a space
        if re.search(r"^(# |## )", v, re.MULTILINE):
            raise ValueError(
                "Level 1 and 2 headings (# and ##) are not allowed. Please use level 3+ headings (###, ####, etc.) instead."
            )
        return v

    def validate_autonomous_schedule(self) -> None:
        """Validate the schedule settings for autonomous configurations.

        This validation ensures:
        1. Only one scheduling method (minutes or cron) is set per autonomous config
        2. The minimum interval is 5 minutes for both types of schedules
        """
        if not self.autonomous:
            return

        for autonomous_config in self.autonomous:
            # Check that exactly one scheduling method is provided
            if not autonomous_config.minutes and not autonomous_config.cron:
                raise HTTPException(
                    status_code=400, detail="either minutes or cron must have a value"
                )

            if autonomous_config.minutes and autonomous_config.cron:
                raise HTTPException(
                    status_code=400, detail="only one of minutes or cron can be set"
                )

            # Validate minimum interval of 5 minutes
            if autonomous_config.minutes and autonomous_config.minutes < 5:
                raise HTTPException(
                    status_code=400,
                    detail="The shortest execution interval is 5 minutes",
                )

            # Validate cron expression to ensure interval is at least 5 minutes
            if autonomous_config.cron:
                # First validate the cron expression format using cron-validator

                try:
                    CronValidator.parse(autonomous_config.cron)
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid cron expression format: {autonomous_config.cron}",
                    )

                parts = autonomous_config.cron.split()
                if len(parts) < 5:
                    raise HTTPException(
                        status_code=400, detail="Invalid cron expression format"
                    )

                minute, hour, day_of_month, month, day_of_week = parts[:5]

                # Check if minutes or hours have too frequent intervals
                if "*" in minute and "*" in hour:
                    # If both minute and hour are wildcards, it would run every minute
                    raise HTTPException(
                        status_code=400,
                        detail="The shortest execution interval is 5 minutes",
                    )

                if "/" in minute:
                    # Check step value in minute field (e.g., */15)
                    step = int(minute.split("/")[1])
                    if step < 5 and hour == "*":
                        raise HTTPException(
                            status_code=400,
                            detail="The shortest execution interval is 5 minutes",
                        )

                # Check for comma-separated values or ranges that might result in multiple executions per hour
                if ("," in minute or "-" in minute) and hour == "*":
                    raise HTTPException(
                        status_code=400,
                        detail="The shortest execution interval is 5 minutes",
                    )

    async def update(self, id: str) -> "Agent":
        # Validate autonomous schedule settings if present
        if "autonomous" in self.model_dump(exclude_unset=True):
            self.validate_autonomous_schedule()

        async with get_session() as db:
            db_agent = await db.get(AgentTable, id)
            if not db_agent:
                raise HTTPException(status_code=404, detail="Agent not found")
            # check owner
            if self.owner and db_agent.owner != self.owner:
                raise HTTPException(
                    status_code=403,
                    detail="You do not have permission to update this agent",
                )
            # update
            for key, value in self.model_dump(exclude_unset=True).items():
                setattr(db_agent, key, value)
            await db.commit()
            await db.refresh(db_agent)
            return Agent.model_validate(db_agent)

    async def override(self, id: str) -> "Agent":
        # Validate autonomous schedule settings if present
        if "autonomous" in self.model_dump(exclude_unset=True):
            self.validate_autonomous_schedule()

        async with get_session() as db:
            db_agent = await db.get(AgentTable, id)
            if not db_agent:
                raise HTTPException(status_code=404, detail="Agent not found")
            # check owner
            if db_agent.owner and db_agent.owner != self.owner:
                raise HTTPException(
                    status_code=403,
                    detail="You do not have permission to update this agent",
                )
            # update
            for key, value in self.model_dump().items():
                setattr(db_agent, key, value)
            await db.commit()
            await db.refresh(db_agent)
            return Agent.model_validate(db_agent)


class AgentCreate(AgentUpdate):
    """Agent create model."""

    id: Annotated[
        str,
        PydanticField(
            default_factory=lambda: str(XID()),
            description="Unique identifier for the agent. Must be URL-safe, containing only lowercase letters, numbers, and hyphens",
            pattern=r"^[a-z][a-z0-9-]*$",
            min_length=2,
            max_length=67,
        ),
    ]

    async def check_upstream_id(self) -> None:
        if not self.upstream_id:
            return None
        async with get_session() as db:
            existing = await db.scalar(
                select(AgentTable).where(AgentTable.upstream_id == self.upstream_id)
            )
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail="Upstream id already in use",
                )

    async def get_by_upstream_id(self) -> Optional["Agent"]:
        if not self.upstream_id:
            return None
        async with get_session() as db:
            existing = await db.scalar(
                select(AgentTable).where(AgentTable.upstream_id == self.upstream_id)
            )
            if existing:
                return Agent.model_validate(existing)
            return None

    async def create(self) -> "Agent":
        # Validate autonomous schedule settings if present
        if self.autonomous:
            self.validate_autonomous_schedule()

        async with get_session() as db:
            db_agent = AgentTable(**self.model_dump())
            db.add(db_agent)
            await db.commit()
            await db.refresh(db_agent)
            return Agent.model_validate(db_agent)

    async def create_or_update(self) -> ("Agent", bool):
        # Validation is now handled by field validators
        await self.check_upstream_id()

        # Validate autonomous schedule settings if present
        if self.autonomous:
            self.validate_autonomous_schedule()

        is_new = False
        async with get_session() as db:
            db_agent = await db.get(AgentTable, self.id)
            if not db_agent:
                db_agent = AgentTable(**self.model_dump())
                db.add(db_agent)
                is_new = True
            else:
                # check owner
                if self.owner and db_agent.owner != self.owner:
                    raise HTTPException(
                        status_code=403,
                        detail="You do not have permission to update this agent",
                    )
                for key, value in self.model_dump(exclude_unset=True).items():
                    setattr(db_agent, key, value)
            await db.commit()
            await db.refresh(db_agent)
            return Agent.model_validate(db_agent), is_new


class Agent(AgentCreate):
    """Agent model."""

    model_config = ConfigDict(from_attributes=True)

    # auto timestamp
    created_at: Annotated[
        datetime,
        PydanticField(
            description="Timestamp when the agent was created, will ignore when importing"
        ),
    ]
    updated_at: Annotated[
        datetime,
        PydanticField(
            description="Timestamp when the agent was last updated, will ignore when importing"
        ),
    ]

    def has_image_parser_skill(self, is_private: bool = False) -> bool:
        if self.skills:
            for skill, skill_config in self.skills.items():
                if skill == "openai" and skill_config.get("enabled"):
                    states = skill_config.get("states", {})
                    if is_private:
                        # Include both private and public when is_private=True
                        if states.get("image_to_text") in ["private", "public"]:
                            return True
                        if states.get("gpt_image_to_image") in ["private", "public"]:
                            return True
                    else:
                        # Only public when is_private=False
                        if states.get("image_to_text") in ["public"]:
                            return True
                        if states.get("gpt_image_to_image") in ["public"]:
                            return True
        return False

    async def is_model_support_image(self) -> bool:
        model = await LLMModelInfo.get(self.model)
        return model.supports_image_input

    def to_yaml(self) -> str:
        """
        Dump the agent model to YAML format with field descriptions as comments.
        The comments are extracted from the field descriptions in the model.
        Fields annotated with SkipJsonSchema will be excluded from the output.
        Only fields from AgentUpdate model are included.
        Deprecated fields with None or empty values are skipped.

        Returns:
            str: YAML representation of the agent with field descriptions as comments
        """
        data = {}
        yaml_lines = []

        def wrap_text(text: str, width: int = 80, prefix: str = "# ") -> list[str]:
            """Wrap text to specified width, preserving existing line breaks."""
            lines = []
            for paragraph in text.split("\n"):
                if not paragraph:
                    lines.append(prefix.rstrip())
                    continue
                # Use textwrap to wrap each paragraph
                wrapped = textwrap.wrap(paragraph, width=width - len(prefix))
                lines.extend(prefix + line for line in wrapped)
            return lines

        # Get the field names from AgentUpdate model for filtering
        agent_update_fields = set(AgentUpdate.model_fields.keys())

        for field_name, field in self.model_fields.items():
            logger.debug(f"Processing field {field_name} with type {field.metadata}")
            # Skip fields that are not in AgentUpdate model
            if field_name not in agent_update_fields:
                continue

            # Skip fields with SkipJsonSchema annotation
            if any(isinstance(item, SkipJsonSchema) for item in field.metadata):
                continue

            value = getattr(self, field_name)

            # Skip deprecated fields with None or empty values
            is_deprecated = hasattr(field, "deprecated") and field.deprecated
            if is_deprecated and not value:
                continue

            data[field_name] = value
            # Add comment from field description if available
            description = field.description
            if description:
                if len(yaml_lines) > 0:  # Add blank line between fields
                    yaml_lines.append("")
                # Split and wrap description into multiple lines
                yaml_lines.extend(wrap_text(description))

            # Check if the field is deprecated and add deprecation notice
            if is_deprecated:
                # Add deprecation message
                if hasattr(field, "deprecation_message") and field.deprecation_message:
                    yaml_lines.extend(
                        wrap_text(f"Deprecated: {field.deprecation_message}")
                    )
                else:
                    yaml_lines.append("# Deprecated")

            # Check if the field is experimental and add experimental notice
            if hasattr(field, "json_schema_extra") and field.json_schema_extra:
                if field.json_schema_extra.get("x-group") == "experimental":
                    yaml_lines.append("# Experimental")

            # Format the value based on its type
            if value is None:
                yaml_lines.append(f"{field_name}: null")
            elif isinstance(value, str):
                if "\n" in value or len(value) > 60:
                    # Use block literal style (|) for multiline strings
                    # Remove any existing escaped newlines and use actual line breaks
                    value = value.replace("\\n", "\n")
                    yaml_value = f"{field_name}: |-\n"
                    # Indent each line with 2 spaces
                    yaml_value += "\n".join(f"  {line}" for line in value.split("\n"))
                    yaml_lines.append(yaml_value)
                else:
                    # Use flow style for short strings
                    yaml_value = yaml.dump(
                        {field_name: value},
                        default_flow_style=False,
                        allow_unicode=True,  # This ensures emojis are preserved
                    )
                    yaml_lines.append(yaml_value.rstrip())
            elif isinstance(value, list) and value and hasattr(value[0], "model_dump"):
                # Handle list of Pydantic models (e.g., List[AgentAutonomous])
                yaml_lines.append(f"{field_name}:")
                # Convert each Pydantic model to dict
                model_dicts = [item.model_dump(exclude_none=True) for item in value]
                # Dump the list of dicts
                yaml_value = yaml.dump(
                    model_dicts, default_flow_style=False, allow_unicode=True
                )
                # Indent all lines and append to yaml_lines
                indented_yaml = "\n".join(
                    f"  {line}" for line in yaml_value.split("\n")
                )
                yaml_lines.append(indented_yaml.rstrip())
            elif hasattr(value, "model_dump"):
                # Handle individual Pydantic model
                model_dict = value.model_dump(exclude_none=True)
                yaml_value = yaml.dump(
                    {field_name: model_dict},
                    default_flow_style=False,
                    allow_unicode=True,
                )
                yaml_lines.append(yaml_value.rstrip())
            else:
                # Handle Decimal values specifically
                if isinstance(value, Decimal):
                    # Convert Decimal to string to avoid !!python/object/apply:decimal.Decimal serialization
                    yaml_lines.append(f"{field_name}: {value}")
                else:
                    # Handle other non-string values
                    yaml_value = yaml.dump(
                        {field_name: value},
                        default_flow_style=False,
                        allow_unicode=True,
                    )
                    yaml_lines.append(yaml_value.rstrip())

        return "\n".join(yaml_lines) + "\n"

    @staticmethod
    async def count() -> int:
        async with get_session() as db:
            return await db.scalar(select(func.count(AgentTable.id)))

    @classmethod
    async def get(cls, agent_id: str) -> Optional["Agent"]:
        async with get_session() as db:
            item = await db.scalar(select(AgentTable).where(AgentTable.id == agent_id))
            if item is None:
                return None
            return cls.model_validate(item)

    def skill_config(self, category: str) -> Dict[str, Any]:
        return self.skills.get(category, {}) if self.skills else {}

    @staticmethod
    def _is_agent_owner_only_skill(skill_schema: Dict[str, Any]) -> bool:
        """Check if a skill requires agent owner API keys only based on its resolved schema."""
        if (
            skill_schema
            and "properties" in skill_schema
            and "api_key_provider" in skill_schema["properties"]
        ):
            api_key_provider = skill_schema["properties"]["api_key_provider"]
            if "enum" in api_key_provider and api_key_provider["enum"] == [
                "agent_owner"
            ]:
                return True
        return False

    @classmethod
    async def get_json_schema(
        cls,
        db: AsyncSession = None,
        filter_owner_api_skills: bool = False,
        admin_llm_skill_control: bool = True,
    ) -> Dict:
        """Get the JSON schema for Agent model with all $ref references resolved.

        This is the shared function that handles admin configuration filtering
        for both the API endpoint and agent generation.

        Args:
            db: Database session (optional, will create if not provided)
            filter_owner_api_skills: Whether to filter out skills that require agent owner API keys
            admin_llm_skill_control: Whether to enable admin LLM and skill control features

        Returns:
            Dict containing the complete JSON schema for the Agent model
        """
        # Get database session if not provided
        if db is None:
            async with get_session() as session:
                return await cls.get_json_schema(
                    session, filter_owner_api_skills, admin_llm_skill_control
                )

        # Get the schema file path relative to this file
        current_dir = Path(__file__).parent
        agent_schema_path = current_dir / "agent_schema.json"

        base_uri = f"file://{agent_schema_path}"
        with open(agent_schema_path) as f:
            schema = jsonref.load(f, base_uri=base_uri, proxies=False, lazy_load=False)

            # Get the model property from the schema
            model_property = schema.get("properties", {}).get("model", {})

            if admin_llm_skill_control:
                # Process model property - use LLMModelInfo as primary source
                if model_property:
                    # Query all LLM models from the database
                    stmt = select(LLMModelInfoTable).where(LLMModelInfoTable.enabled)
                    result = await db.execute(stmt)
                    models = result.scalars().all()

                    # Create new lists based on LLMModelInfo
                    new_enum = []
                    new_enum_title = []
                    new_enum_category = []
                    new_enum_support_skill = []

                    # Process each model from database
                    for model in models:
                        model_info = LLMModelInfo.model_validate(model)

                        # Add model ID to enum
                        new_enum.append(model_info.id)

                        # Add model name as title
                        new_enum_title.append(model_info.name)

                        # Add provider display name as category
                        provider = (
                            LLMProvider(model_info.provider)
                            if isinstance(model_info.provider, str)
                            else model_info.provider
                        )
                        new_enum_category.append(provider.display_name())

                        # Add skill support information
                        new_enum_support_skill.append(model_info.supports_skill_calls)

                    # Update the schema with the new lists constructed from LLMModelInfo
                    model_property["enum"] = new_enum
                    model_property["x-enum-title"] = new_enum_title
                    model_property["x-enum-category"] = new_enum_category
                    model_property["x-support-skill"] = new_enum_support_skill

                    # If the default model is not in the new enum, update it if possible
                    if (
                        "default" in model_property
                        and model_property["default"] not in new_enum
                        and new_enum
                    ):
                        model_property["default"] = new_enum[0]

                # Process skills property
                skills_property = schema.get("properties", {}).get("skills", {})
                skills_properties = skills_property.get("properties", {})

                if skills_properties:
                    # Load all skills from the database
                    # Query all skills grouped by category with enabled status
                    stmt = select(
                        SkillTable.category,
                        func.bool_or(SkillTable.enabled).label("any_enabled"),
                    ).group_by(SkillTable.category)
                    result = await db.execute(stmt)
                    category_status = {row.category: row.any_enabled for row in result}

                    # Query all skills with their price levels for adding x-price-level fields
                    skills_stmt = select(
                        SkillTable.category,
                        SkillTable.config_name,
                        SkillTable.price_level,
                        SkillTable.enabled,
                    ).where(SkillTable.enabled)
                    skills_result = await db.execute(skills_stmt)
                    skills_data = {}
                    category_price_levels = {}

                    for row in skills_result:
                        if row.category not in skills_data:
                            skills_data[row.category] = {}
                            category_price_levels[row.category] = []

                        if row.config_name:
                            skills_data[row.category][row.config_name] = row.price_level

                        if row.price_level is not None:
                            category_price_levels[row.category].append(row.price_level)

                    # Calculate average price levels for categories
                    category_avg_price_levels = {}
                    for category, price_levels in category_price_levels.items():
                        if price_levels:
                            avg_price_level = int(sum(price_levels) / len(price_levels))
                            category_avg_price_levels[category] = avg_price_level

                    # Create a copy of keys to avoid modifying during iteration
                    skill_keys = list(skills_properties.keys())

                    # Process each skill in the schema
                    for skill_category in skill_keys:
                        if skill_category not in category_status:
                            # If category not found in database, remove it from schema
                            skills_properties.pop(skill_category, None)
                        elif not category_status[skill_category]:
                            # If category exists but all skills are disabled, remove it
                            skills_properties.pop(skill_category, None)
                        elif filter_owner_api_skills and cls._is_agent_owner_only_skill(
                            skills_properties[skill_category]
                        ):
                            # If filtering owner API skills and this skill requires it, remove it
                            skills_properties.pop(skill_category, None)
                            logger.info(
                                f"Filtered out skill '{skill_category}' from auto-generation: requires agent owner API key"
                            )
                        else:
                            # Add x-avg-price-level to category level
                            if skill_category in category_avg_price_levels:
                                skills_properties[skill_category][
                                    "x-avg-price-level"
                                ] = category_avg_price_levels[skill_category]

                            # Add x-price-level to individual skill states
                            if skill_category in skills_data:
                                skill_states = (
                                    skills_properties[skill_category]
                                    .get("properties", {})
                                    .get("states", {})
                                    .get("properties", {})
                                )
                                for state_name, state_config in skill_states.items():
                                    if (
                                        state_name in skills_data[skill_category]
                                        and skills_data[skill_category][state_name]
                                        is not None
                                    ):
                                        state_config["x-price-level"] = skills_data[
                                            skill_category
                                        ][state_name]

            # Log the changes for debugging
            logger.debug(
                f"Schema processed with LLM and skill controls enabled: {admin_llm_skill_control}, "
                f"filtered owner API skills: {filter_owner_api_skills}"
            )

            return schema


class AgentResponse(BaseModel):
    """Response model for Agent API."""

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda dt: dt.isoformat(),
        },
    )

    id: Annotated[
        str,
        PydanticField(
            description="Unique identifier for the agent. Must be URL-safe, containing only lowercase letters, numbers, and hyphens",
        ),
    ]
    # auto timestamp
    created_at: Annotated[
        datetime,
        PydanticField(
            description="Timestamp when the agent was created, will ignore when importing"
        ),
    ]
    updated_at: Annotated[
        datetime,
        PydanticField(
            description="Timestamp when the agent was last updated, will ignore when importing"
        ),
    ]
    # Agent part
    name: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Display name of the agent",
        ),
    ]
    slug: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Slug of the agent, used for URL generation",
        ),
    ]
    description: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Description of the agent, for public view, not contained in prompt",
        ),
    ]
    external_website: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Link of external website of the agent, if you have one",
        ),
    ]
    picture: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Picture of the agent",
        ),
    ]
    ticker: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Ticker symbol of the agent",
        ),
    ]
    token_address: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Token address of the agent",
        ),
    ]
    token_pool: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Pool of the agent token",
        ),
    ]
    mode: Annotated[
        Optional[Literal["public", "private"]],
        PydanticField(
            default=None,
            description="Mode of the agent, public or private",
        ),
    ]
    fee_percentage: Annotated[
        Optional[Decimal],
        PydanticField(
            default=None,
            description="Fee percentage of the agent",
        ),
    ]
    owner: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Owner identifier of the agent, used for access control",
            max_length=50,
            json_schema_extra={
                "x-group": "internal",
            },
        ),
    ]
    upstream_id: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="External reference ID for idempotent operations",
            max_length=100,
            json_schema_extra={
                "x-group": "internal",
            },
        ),
    ]
    upstream_extra: Annotated[
        Optional[Dict[str, Any]],
        PydanticField(
            default=None,
            description="Additional data store for upstream use",
        ),
    ]
    # AI part
    model: Annotated[
        str,
        PydanticField(
            description="AI model identifier to be used by this agent for processing requests. Available models: gpt-4o, gpt-4o-mini, deepseek-chat, deepseek-reasoner, grok-2, eternalai, reigent",
        ),
    ]
    # autonomous mode
    autonomous: Annotated[
        Optional[List[Dict[str, Any]]],
        PydanticField(
            default=None,
            description=("Autonomous agent configurations."),
        ),
    ]
    # agent examples
    example_intro: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Introduction for example interactions",
        ),
    ]
    examples: Annotated[
        Optional[List[AgentExample]],
        PydanticField(
            default=None,
            description="List of example prompts for the agent",
        ),
    ]
    # skills
    skills: Annotated[
        Optional[Dict[str, Any]],
        PydanticField(
            default=None,
            description="Dict of skills and their corresponding configurations",
        ),
    ]
    wallet_provider: Annotated[
        Optional[Literal["cdp", "readonly"]],
        PydanticField(
            default="cdp",
            description="Provider of the agent's wallet",
        ),
    ]
    network_id: Annotated[
        Optional[str],
        PydanticField(
            default="base-mainnet",
            description="Network identifier",
        ),
    ]
    cdp_network_id: Annotated[
        Optional[str],
        PydanticField(
            default="base-mainnet",
            description="Network identifier for CDP integration",
        ),
    ]
    # telegram entrypoint
    telegram_entrypoint_enabled: Annotated[
        Optional[bool],
        PydanticField(
            default=False,
            description="Whether the agent can play telegram bot",
        ),
    ]

    # data part
    cdp_wallet_address: Annotated[
        Optional[str], PydanticField(description="CDP wallet address for the agent")
    ]
    evm_wallet_address: Annotated[
        Optional[str], PydanticField(description="EVM wallet address for the agent")
    ]
    solana_wallet_address: Annotated[
        Optional[str], PydanticField(description="Solana wallet address for the agent")
    ]
    has_twitter_linked: Annotated[
        bool,
        PydanticField(description="Whether the agent has linked their Twitter account"),
    ]
    linked_twitter_username: Annotated[
        Optional[str],
        PydanticField(description="The username of the linked Twitter account"),
    ]
    linked_twitter_name: Annotated[
        Optional[str],
        PydanticField(description="The name of the linked Twitter account"),
    ]
    has_twitter_self_key: Annotated[
        bool,
        PydanticField(
            description="Whether the agent has self-keyed their Twitter account"
        ),
    ]
    has_telegram_self_key: Annotated[
        bool,
        PydanticField(
            description="Whether the agent has self-keyed their Telegram account"
        ),
    ]
    linked_telegram_username: Annotated[
        Optional[str],
        PydanticField(description="The username of the linked Telegram account"),
    ]
    linked_telegram_name: Annotated[
        Optional[str],
        PydanticField(description="The name of the linked Telegram account"),
    ]
    accept_image_input: Annotated[
        bool,
        PydanticField(
            description="Whether the agent accepts image inputs in public mode"
        ),
    ]
    accept_image_input_private: Annotated[
        bool,
        PydanticField(
            description="Whether the agent accepts image inputs in private mode"
        ),
    ]

    def etag(self) -> str:
        """Generate an ETag for this agent response.

        The ETag is based on a hash of the entire object to ensure it changes
        whenever any part of the agent is modified.

        Returns:
            str: ETag value for the agent
        """
        import hashlib

        # Generate hash from the entire object data using json mode to handle datetime objects
        # Sort keys to ensure consistent ordering of dictionary keys
        data = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return f"{hashlib.md5(data.encode()).hexdigest()}"

    @classmethod
    async def from_agent(
        cls, agent: Agent, agent_data: Optional[AgentData] = None
    ) -> "AgentResponse":
        """Create an AgentResponse from an Agent instance.

        Args:
            agent: Agent instance
            agent_data: Optional AgentData instance

        Returns:
            AgentResponse: Response model with additional processed data
        """
        # Get base data from agent
        data = agent.model_dump()

        # Filter sensitive fields from autonomous list
        if data.get("autonomous"):
            filtered_autonomous = []
            for item in data["autonomous"]:
                if isinstance(item, dict):
                    filtered_item = {
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "enabled": item.get("enabled"),
                    }
                    filtered_autonomous.append(filtered_item)
            data["autonomous"] = filtered_autonomous

        # Filter sensitive fields from skills dictionary
        if data.get("skills"):
            filtered_skills = {}
            for skill_name, skill_config in data["skills"].items():
                if isinstance(skill_config, dict):
                    # Only include skills that are enabled
                    if skill_config.get("enabled") is True:
                        filtered_config = {"enabled": True}
                        # Only keep states with public or private values
                        if "states" in skill_config and isinstance(
                            skill_config["states"], dict
                        ):
                            filtered_states = {}
                            for state_key, state_value in skill_config[
                                "states"
                            ].items():
                                if state_value in ["public", "private"]:
                                    filtered_states[state_key] = state_value
                            if filtered_states:
                                filtered_config["states"] = filtered_states
                        filtered_skills[skill_name] = filtered_config
            data["skills"] = filtered_skills

        # Process CDP wallet address
        cdp_wallet_address = agent_data.evm_wallet_address if agent_data else None
        evm_wallet_address = agent_data.evm_wallet_address if agent_data else None
        solana_wallet_address = agent_data.solana_wallet_address if agent_data else None

        # Process Twitter linked status
        has_twitter_linked = False
        linked_twitter_username = None
        linked_twitter_name = None
        if agent_data and agent_data.twitter_access_token:
            linked_twitter_username = agent_data.twitter_username
            linked_twitter_name = agent_data.twitter_name
            if agent_data.twitter_access_token_expires_at:
                has_twitter_linked = (
                    agent_data.twitter_access_token_expires_at
                    > datetime.now(timezone.utc)
                )
            else:
                has_twitter_linked = True

        # Process Twitter self-key status
        has_twitter_self_key = bool(
            agent_data and agent_data.twitter_self_key_refreshed_at
        )

        # Process Telegram self-key status and remove token
        linked_telegram_username = None
        linked_telegram_name = None
        telegram_config = data.get("telegram_config", {})
        has_telegram_self_key = bool(
            telegram_config and "token" in telegram_config and telegram_config["token"]
        )
        if telegram_config and "token" in telegram_config:
            if agent_data:
                linked_telegram_username = agent_data.telegram_username
                linked_telegram_name = agent_data.telegram_name

        accept_image_input = (
            await agent.is_model_support_image() or agent.has_image_parser_skill()
        )
        accept_image_input_private = (
            await agent.is_model_support_image()
            or agent.has_image_parser_skill(is_private=True)
        )

        # Add processed fields to response
        data.update(
            {
                "cdp_wallet_address": cdp_wallet_address,
                "evm_wallet_address": evm_wallet_address,
                "solana_wallet_address": solana_wallet_address,
                "has_twitter_linked": has_twitter_linked,
                "linked_twitter_username": linked_twitter_username,
                "linked_twitter_name": linked_twitter_name,
                "has_twitter_self_key": has_twitter_self_key,
                "has_telegram_self_key": has_telegram_self_key,
                "linked_telegram_username": linked_telegram_username,
                "linked_telegram_name": linked_telegram_name,
                "accept_image_input": accept_image_input,
                "accept_image_input_private": accept_image_input_private,
            }
        )

        return cls.model_validate(data)
