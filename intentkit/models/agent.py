import hashlib
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
from intentkit.models.agent_data import AgentData
from intentkit.models.base import Base
from intentkit.models.credit import CreditAccount
from intentkit.models.db import get_session
from intentkit.models.llm import LLMModelInfo, LLMProvider
from intentkit.models.skill import Skill
from intentkit.utils.error import IntentKitAPIError
from pydantic import BaseModel, ConfigDict, field_validator
from pydantic import Field as PydanticField
from pydantic.json_schema import SkipJsonSchema
from pydantic.main import IncEx
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
from sqlalchemy.exc import IntegrityError
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


class AgentExample(BaseModel):
    """Agent example configuration."""

    name: Annotated[
        str,
        PydanticField(
            description="Name of the example",
            max_length=50,
            json_schema_extra={
                "x-placeholder": "Add a name for the example",
            },
        ),
    ]
    description: Annotated[
        str,
        PydanticField(
            description="Description of the example",
            max_length=200,
            json_schema_extra={
                "x-placeholder": "Add a short description for the example",
            },
        ),
    ]
    prompt: Annotated[
        str,
        PydanticField(
            description="Example prompt",
            max_length=2000,
            json_schema_extra={
                "x-placeholder": "The prompt will be sent to the agent",
            },
        ),
    ]


class AgentUserInputColumns:
    """Abstract base class containing columns that are common to AgentTable and other tables."""

    __abstract__ = True

    # Basic information fields from AgentCore
    name = Column(
        String,
        nullable=True,
        comment="Display name of the agent",
    )
    picture = Column(
        String,
        nullable=True,
        comment="Picture of the agent",
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

    # AI model configuration fields from AgentCore
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

    # Wallet and network configuration fields from AgentCore
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

    # Skills configuration from AgentCore
    skills = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Dict of skills and their corresponding configurations",
    )

    # Additional fields from AgentUserInput
    short_term_memory_strategy = Column(
        String,
        nullable=True,
        default="trim",
        comment="Strategy for managing short-term memory when context limit is reached. 'trim' removes oldest messages, 'summarize' creates summaries.",
    )
    autonomous = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Autonomous agent configurations",
    )
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


class AgentTable(Base, AgentUserInputColumns):
    """Agent table db model."""

    __tablename__ = "agents"

    id = Column(
        String,
        primary_key=True,
        comment="Unique identifier for the agent. Must be URL-safe, containing only lowercase letters, numbers, and hyphens",
    )
    slug = Column(
        String,
        nullable=True,
        comment="Slug of the agent, used for URL generation",
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
    version = Column(
        String,
        nullable=True,
        comment="Version hash of the agent",
    )
    statistics = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Statistics of the agent, update every 1 hour for query",
    )
    assets = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Assets of the agent, update every 1 hour for query",
    )
    account_snapshot = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Account snapshot of the agent, update every 1 hour for query",
    )
    extra = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Other helper data fields for query, come from agent and agent data",
    )

    # Fields moved from AgentUserInputColumns that are no longer in AgentUserInput
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
    fee_percentage = Column(
        Numeric(22, 4),
        nullable=True,
        comment="Fee percentage of the agent",
    )
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
    public_extra = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Public extra data of the agent",
    )
    deployed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the agent was deployed",
    )
    public_info_updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the agent public info was last updated",
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


class AgentCore(BaseModel):
    """Agent core model."""

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
    wallet_provider: Annotated[
        Optional[Literal["cdp", "readonly"]],
        PydanticField(
            default="cdp",
            description="Provider of the agent's wallet",
            json_schema_extra={
                "x-group": "onchain",
            },
        ),
    ] = "cdp"
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


class AgentUserInput(AgentCore):
    """Agent update model."""

    model_config = ConfigDict(
        title="AgentUserInput",
        from_attributes=True,
        json_schema_extra={
            "required": ["name"],
        },
    )

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


class AgentUpdate(AgentUserInput):
    """Agent update model."""

    model_config = ConfigDict(
        title="Agent",
        from_attributes=True,
        json_schema_extra={
            "required": ["name"],
        },
    )

    upstream_id: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="External reference ID for idempotent operations",
            max_length=100,
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
                raise IntentKitAPIError(
                    status_code=400,
                    key="InvalidAutonomousConfig",
                    message="either minutes or cron must have a value",
                )

            if autonomous_config.minutes and autonomous_config.cron:
                raise IntentKitAPIError(
                    status_code=400,
                    key="InvalidAutonomousConfig",
                    message="only one of minutes or cron can be set",
                )

            # Validate minimum interval of 5 minutes
            if autonomous_config.minutes and autonomous_config.minutes < 5:
                raise IntentKitAPIError(
                    status_code=400,
                    key="InvalidAutonomousInterval",
                    message="The shortest execution interval is 5 minutes",
                )

            # Validate cron expression to ensure interval is at least 5 minutes
            if autonomous_config.cron:
                # First validate the cron expression format using cron-validator

                try:
                    CronValidator.parse(autonomous_config.cron)
                except ValueError:
                    raise IntentKitAPIError(
                        status_code=400,
                        key="InvalidCronExpression",
                        message=f"Invalid cron expression format: {autonomous_config.cron}",
                    )

                parts = autonomous_config.cron.split()
                if len(parts) < 5:
                    raise IntentKitAPIError(
                        status_code=400,
                        key="InvalidCronExpression",
                        message="Invalid cron expression format",
                    )

                minute, hour, day_of_month, month, day_of_week = parts[:5]

                # Check if minutes or hours have too frequent intervals
                if "*" in minute and "*" in hour:
                    # If both minute and hour are wildcards, it would run every minute
                    raise IntentKitAPIError(
                        status_code=400,
                        key="InvalidAutonomousInterval",
                        message="The shortest execution interval is 5 minutes",
                    )

                if "/" in minute:
                    # Check step value in minute field (e.g., */15)
                    step = int(minute.split("/")[1])
                    if step < 5 and hour == "*":
                        raise IntentKitAPIError(
                            status_code=400,
                            key="InvalidAutonomousInterval",
                            message="The shortest execution interval is 5 minutes",
                        )

                # Check for comma-separated values or ranges that might result in multiple executions per hour
                if ("," in minute or "-" in minute) and hour == "*":
                    raise IntentKitAPIError(
                        status_code=400,
                        key="InvalidAutonomousInterval",
                        message="The shortest execution interval is 5 minutes",
                    )

    # deprecated, use override instead
    async def update(self, id: str) -> "Agent":
        # Validate autonomous schedule settings if present
        if "autonomous" in self.model_dump(exclude_unset=True):
            self.validate_autonomous_schedule()

        async with get_session() as db:
            db_agent = await db.get(AgentTable, id)
            if not db_agent:
                raise IntentKitAPIError(
                    status_code=404,
                    key="AgentNotFound",
                    message="Agent not found",
                )
            # update
            for key, value in self.model_dump(exclude_unset=True).items():
                setattr(db_agent, key, value)
            db_agent.version = self.hash()
            db_agent.deployed_at = func.now()
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
                raise IntentKitAPIError(
                    status_code=404,
                    key="AgentNotFound",
                    message="Agent not found",
                )
            # update
            for key, value in self.model_dump().items():
                setattr(db_agent, key, value)
            # version
            db_agent.version = self.hash()
            db_agent.deployed_at = func.now()
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
    owner: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Owner identifier of the agent, used for access control",
            max_length=50,
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
                raise IntentKitAPIError(
                    status_code=400,
                    key="UpstreamIdConflict",
                    message="Upstream id already in use",
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
            try:
                db_agent = AgentTable(**self.model_dump())
                db_agent.version = self.hash()
                db_agent.deployed_at = func.now()
                db.add(db_agent)
                await db.commit()
                await db.refresh(db_agent)
                return Agent.model_validate(db_agent)
            except IntegrityError:
                await db.rollback()
                raise IntentKitAPIError(
                    status_code=400,
                    key="AgentExists",
                    message=f"Agent with ID '{self.id}' already exists",
                )


class AgentPublicInfo(BaseModel):
    """Public information of the agent."""

    model_config = ConfigDict(
        title="AgentPublicInfo",
        from_attributes=True,
    )

    description: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Description of the agent, for public view, not contained in prompt",
            json_schema_extra={
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
                "x-placeholder": "Enter agent external website url",
                "format": "uri",
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
                "x-placeholder": "The contract address of the agent token",
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
                "x-placeholder": "The contract address of the agent token pool",
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
                "x-placeholder": "Agent will charge service fee according to this ratio.",
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
                "x-placeholder": "Add a short introduction in new chat",
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
                "x-inline": True,
            },
        ),
    ]
    public_extra: Annotated[
        Optional[Dict[str, Any]],
        PydanticField(
            default=None,
            description="Public extra data of the agent",
        ),
    ]

    async def override(self, agent_id: str) -> "Agent":
        """Override agent public info with all fields from this instance.

        Args:
            agent_id: The ID of the agent to override

        Returns:
            The updated Agent instance
        """
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


class Agent(AgentCreate, AgentPublicInfo):
    """Agent model."""

    model_config = ConfigDict(from_attributes=True)

    slug: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Slug of the agent, used for URL generation",
            max_length=20,
            min_length=2,
        ),
    ]
    version: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Version hash of the agent",
        ),
    ]
    statistics: Annotated[
        Optional[Dict[str, Any]],
        PydanticField(
            description="Statistics of the agent, update every 1 hour for query"
        ),
    ]
    assets: Annotated[
        Optional[Dict[str, Any]],
        PydanticField(description="Assets of the agent, update every 1 hour for query"),
    ]
    account_snapshot: Annotated[
        Optional[CreditAccount],
        PydanticField(
            description="Account snapshot of the agent, update every 1 hour for query"
        ),
    ]
    extra: Annotated[
        Optional[Dict[str, Any]],
        PydanticField(
            description="Other helper data fields for query, come from agent and agent data"
        ),
    ]
    deployed_at: Annotated[
        Optional[datetime],
        PydanticField(
            default=None,
            description="Timestamp when the agent was deployed",
        ),
    ]
    public_info_updated_at: Annotated[
        Optional[datetime],
        PydanticField(
            default=None,
            description="Timestamp when the agent public info was last updated",
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
                yaml_lines.append(f"{field_name}:")
                yaml_value = yaml.dump(
                    value.model_dump(exclude_none=True),
                    default_flow_style=False,
                    allow_unicode=True,
                )
                # Indent all lines and append to yaml_lines
                indented_yaml = "\n".join(
                    f"  {line}" for line in yaml_value.split("\n") if line.strip()
                )
                yaml_lines.append(indented_yaml)
            else:
                # Handle Decimal and other types
                if isinstance(value, Decimal):
                    yaml_lines.append(f"{field_name}: {str(value)}")
                else:
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
    ) -> Dict:
        """Get the JSON schema for Agent model with all $ref references resolved.

        This is the shared function that handles admin configuration filtering
        for both the API endpoint and agent generation.

        Args:
            db: Database session (optional, will create if not provided)
            filter_owner_api_skills: Whether to filter out skills that require agent owner API keys

        Returns:
            Dict containing the complete JSON schema for the Agent model
        """
        # Get database session if not provided
        if db is None:
            async with get_session() as session:
                return await cls.get_json_schema(session, filter_owner_api_skills)

        # Get the schema file path relative to this file
        current_dir = Path(__file__).parent
        agent_schema_path = current_dir / "agent_schema.json"

        base_uri = f"file://{agent_schema_path}"
        with open(agent_schema_path) as f:
            schema = jsonref.load(f, base_uri=base_uri, proxies=False, lazy_load=False)

            # Get the model property from the schema
            model_property = schema.get("properties", {}).get("model", {})

            # Process model property using defaults merged with database overrides
            if model_property:
                new_enum = []
                new_enum_title = []
                new_enum_category = []
                new_enum_support_skill = []

                for model_info in await LLMModelInfo.get_all(db):
                    if not model_info.enabled:
                        continue

                    provider = (
                        LLMProvider(model_info.provider)
                        if isinstance(model_info.provider, str)
                        else model_info.provider
                    )

                    new_enum.append(model_info.id)
                    new_enum_title.append(model_info.name)
                    new_enum_category.append(provider.display_name())
                    new_enum_support_skill.append(model_info.supports_skill_calls)

                model_property["enum"] = new_enum
                model_property["x-enum-title"] = new_enum_title
                model_property["x-enum-category"] = new_enum_category
                model_property["x-support-skill"] = new_enum_support_skill

                if (
                    "default" in model_property
                    and model_property["default"] not in new_enum
                    and new_enum
                ):
                    model_property["default"] = new_enum[0]

            # Process skills property using defaults merged with database overrides
            skills_property = schema.get("properties", {}).get("skills", {})
            skills_properties = skills_property.get("properties", {})

            if skills_properties:
                skill_states_map: dict[str, dict[str, Skill]] = {}

                for skill_model in await Skill.get_all(db):
                    if not skill_model.config_name:
                        continue
                    category_states = skill_states_map.setdefault(
                        skill_model.category, {}
                    )
                    if skill_model.enabled:
                        category_states[skill_model.config_name] = skill_model
                    else:
                        category_states.pop(skill_model.config_name, None)

                enabled_categories = {
                    category for category, states in skill_states_map.items() if states
                }

                category_avg_price_levels = {}
                skills_data = {}
                for category, states in skill_states_map.items():
                    if not states:
                        continue
                    price_levels = [
                        state.price_level
                        for state in states.values()
                        if state.price_level is not None
                    ]
                    if price_levels:
                        category_avg_price_levels[category] = int(
                            sum(price_levels) / len(price_levels)
                        )
                    skills_data[category] = {
                        config_name: state.price_level
                        for config_name, state in states.items()
                    }

                skill_keys = list(skills_properties.keys())

                for skill_category in skill_keys:
                    if skill_category not in enabled_categories:
                        skills_properties.pop(skill_category, None)
                    elif filter_owner_api_skills and cls._is_agent_owner_only_skill(
                        skills_properties[skill_category]
                    ):
                        skills_properties.pop(skill_category, None)
                        logger.info(
                            f"Filtered out skill '{skill_category}' from auto-generation: requires agent owner API key"
                        )
                    else:
                        if skill_category in category_avg_price_levels:
                            skills_properties[skill_category]["x-avg-price-level"] = (
                                category_avg_price_levels[skill_category]
                            )

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
                "Schema processed with merged LLM/skill defaults; filtered owner API skills: %s",
                filter_owner_api_skills,
            )

            return schema


class AgentResponse(Agent):
    """Agent response model that excludes sensitive fields from JSON output and schema."""

    model_config = ConfigDict(
        title="AgentPublic",
        from_attributes=True,
        # json_encoders={
        #     datetime: lambda v: v.isoformat(timespec="milliseconds"),
        # },
    )

    # Override privacy fields to exclude them from JSON schema
    purpose: SkipJsonSchema[Optional[str]] = None
    personality: SkipJsonSchema[Optional[str]] = None
    principles: SkipJsonSchema[Optional[str]] = None
    prompt: SkipJsonSchema[Optional[str]] = None
    prompt_append: SkipJsonSchema[Optional[str]] = None
    temperature: SkipJsonSchema[Optional[float]] = None
    frequency_penalty: SkipJsonSchema[Optional[float]] = None
    telegram_entrypoint_prompt: SkipJsonSchema[Optional[str]] = None
    telegram_config: SkipJsonSchema[Optional[dict]] = None
    xmtp_entrypoint_prompt: SkipJsonSchema[Optional[str]] = None

    # Additional fields specific to AgentResponse
    cdp_wallet_address: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="CDP wallet address of the agent",
        ),
    ]
    evm_wallet_address: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="EVM wallet address of the agent",
        ),
    ]
    solana_wallet_address: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Solana wallet address of the agent",
        ),
    ]
    has_twitter_linked: Annotated[
        bool,
        PydanticField(
            default=False,
            description="Whether the agent has Twitter linked",
        ),
    ]
    linked_twitter_username: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Linked Twitter username",
        ),
    ]
    linked_twitter_name: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Linked Twitter display name",
        ),
    ]
    has_twitter_self_key: Annotated[
        bool,
        PydanticField(
            default=False,
            description="Whether the agent has Twitter self key",
        ),
    ]
    has_telegram_self_key: Annotated[
        bool,
        PydanticField(
            default=False,
            description="Whether the agent has Telegram self key",
        ),
    ]
    linked_telegram_username: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Linked Telegram username",
        ),
    ]
    linked_telegram_name: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Linked Telegram display name",
        ),
    ]
    accept_image_input: Annotated[
        bool,
        PydanticField(
            default=False,
            description="Whether the agent accepts image input",
        ),
    ]
    accept_image_input_private: Annotated[
        bool,
        PydanticField(
            default=False,
            description="Whether the agent accepts image input in private mode",
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

        # Process Telegram self-key status
        linked_telegram_username = None
        linked_telegram_name = None
        telegram_config = agent.telegram_config or {}
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

        # Create AgentResponse instance directly from agent with additional fields
        return cls(
            # Copy all fields from agent
            **agent.model_dump(),
            # Add computed fields
            cdp_wallet_address=cdp_wallet_address,
            evm_wallet_address=evm_wallet_address,
            solana_wallet_address=solana_wallet_address,
            has_twitter_linked=has_twitter_linked,
            linked_twitter_username=linked_twitter_username,
            linked_twitter_name=linked_twitter_name,
            has_twitter_self_key=has_twitter_self_key,
            has_telegram_self_key=has_telegram_self_key,
            linked_telegram_username=linked_telegram_username,
            linked_telegram_name=linked_telegram_name,
            accept_image_input=accept_image_input,
            accept_image_input_private=accept_image_input_private,
        )

    def model_dump(
        self,
        *,
        mode: str | Literal["json", "python"] = "python",
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        context: Any | None = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool | Literal["none", "warn", "error"] = True,
        serialize_as_any: bool = False,
    ) -> dict[str, Any]:
        """Override model_dump to exclude privacy fields and filter data."""
        # Get the base model dump
        data = super().model_dump(
            mode=mode,
            include=include,
            exclude=exclude,
            context=context,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
            serialize_as_any=serialize_as_any,
        )

        # Remove privacy fields that might still be present
        privacy_fields = {
            "purpose",
            "personality",
            "principles",
            "prompt",
            "prompt_append",
            "temperature",
            "frequency_penalty",
            "telegram_entrypoint_prompt",
            "telegram_config",
            "xmtp_entrypoint_prompt",
        }
        for field in privacy_fields:
            data.pop(field, None)

        # Filter autonomous list to only keep safe fields
        if "autonomous" in data and data["autonomous"]:
            filtered_autonomous = []
            for item in data["autonomous"]:
                if isinstance(item, dict):
                    # Only keep safe fields: id, name, description, enabled
                    filtered_item = {
                        key: item[key]
                        for key in ["id", "name", "description", "enabled"]
                        if key in item
                    }
                    filtered_autonomous.append(filtered_item)
                else:
                    # Handle AgentAutonomous objects
                    item_dict = (
                        item.model_dump() if hasattr(item, "model_dump") else dict(item)
                    )
                    # Only keep safe fields: id, name, description, enabled
                    filtered_item = {
                        key: item_dict[key]
                        for key in ["id", "name", "description", "enabled"]
                        if key in item_dict
                    }
                    filtered_autonomous.append(filtered_item)
            data["autonomous"] = filtered_autonomous

        # Convert examples to AgentExample instances if they're dictionaries
        if "examples" in data and data["examples"]:
            converted_examples = []
            for example in data["examples"]:
                if isinstance(example, dict):
                    converted_examples.append(AgentExample(**example).model_dump())
                else:
                    converted_examples.append(
                        example.model_dump()
                        if hasattr(example, "model_dump")
                        else example
                    )
            data["examples"] = converted_examples

        # Filter skills to only include enabled ones with specific configurations
        if "skills" in data and data["skills"]:
            filtered_skills = {}
            for skill_name, skill_config in data["skills"].items():
                if (
                    isinstance(skill_config, dict)
                    and skill_config.get("enabled") is True
                ):
                    # Filter out disabled states from the skill configuration
                    original_states = skill_config.get("states", {})
                    filtered_states = {
                        state_name: state_value
                        for state_name, state_value in original_states.items()
                        if state_value != "disabled"
                    }

                    # Only include the skill if it has at least one non-disabled state
                    if filtered_states:
                        filtered_config = {
                            "enabled": skill_config["enabled"],
                            "states": filtered_states,
                        }
                        # Add other non-sensitive config fields if needed
                        for key in ["public", "private"]:
                            if key in skill_config:
                                filtered_config[key] = skill_config[key]
                        filtered_skills[skill_name] = filtered_config
            data["skills"] = filtered_skills

        return data

    def model_dump_json(
        self,
        *,
        indent: int | str | None = None,
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        context: Any | None = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool | Literal["none", "warn", "error"] = True,
        serialize_as_any: bool = False,
    ) -> str:
        """Override model_dump_json to exclude privacy fields and filter sensitive data."""
        # Get the filtered data using the same logic as model_dump
        data = self.model_dump(
            mode="json",
            include=include,
            exclude=exclude,
            context=context,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
            serialize_as_any=serialize_as_any,
        )

        # Use json.dumps to serialize the filtered data with proper indentation
        return json.dumps(data, indent=indent, ensure_ascii=False)
