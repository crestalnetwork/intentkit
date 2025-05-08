import json
import logging
import re
import textwrap
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, Dict, List, Literal, Optional

import yaml
from cron_validator import CronValidator
from epyxid import XID
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pydantic import Field as PydanticField
from pydantic.json_schema import SkipJsonSchema
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    Identity,
    Numeric,
    String,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from models.base import Base
from models.db import get_session

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
        if v is not None and len(v.encode()) > 2000:
            raise ValueError("prompt must be at most 2000 bytes")
        return v

    @model_validator(mode="after")
    def validate_schedule(self) -> "AgentAutonomous":
        # This validator is kept for backward compatibility
        # The actual validation now happens in AgentUpdate.validate_autonomous_schedule
        return self


class AgentTable(Base):
    """Agent table db model."""

    __tablename__ = "agents"

    id = Column(
        String,
        primary_key=True,
        comment="Unique identifier for the agent. Must be URL-safe, containing only lowercase letters, numbers, and hyphens",
    )
    number = Column(
        BigInteger,
        Identity(start=1, increment=1),
        nullable=False,
        comment="Auto-incrementing number assigned by the system for easy reference",
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
        JSONB,
        nullable=True,
        comment="Additional data store for upstream use",
    )
    wallet_provider = Column(
        String,
        nullable=True,
        comment="Provider of the agent's wallet",
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
        default="gpt-4o-mini",
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
    # autonomous mode
    autonomous = Column(
        JSONB,
        nullable=True,
        comment="Autonomous agent configurations",
    )
    # skills
    skills = Column(
        JSONB,
        nullable=True,
        comment="Dict of skills and their corresponding configurations",
    )
    # if cdp_enabled, agent will have a cdp wallet
    cdp_enabled = Column(
        Boolean,
        nullable=True,
        default=False,
        comment="Whether CDP (Crestal Development Platform) integration is enabled",
    )
    cdp_skills = Column(
        ARRAY(String),
        nullable=True,
        comment="List of CDP skills available to this agent",
    )
    cdp_network_id = Column(
        String,
        nullable=True,
        default="base-mainnet",
        comment="Network identifier for CDP integration",
    )
    # if goat_enabled, will load goat skills
    crossmint_config = Column(
        JSONB,
        nullable=True,
        comment="Dict of Crossmint wallet configurations",
    )
    goat_enabled = Column(
        Boolean,
        nullable=True,
        default=False,
        comment="Whether GOAT integration is enabled",
    )
    goat_skills = Column(
        JSONB,
        nullable=True,
        comment="Dict of GOAT skills and their corresponding configurations",
    )
    # if twitter_enabled, the twitter_entrypoint will be enabled, twitter_config will be checked
    twitter_entrypoint_enabled = Column(
        Boolean,
        nullable=True,
        default=False,
        comment="Dangerous, reply all mentions from x.com",
    )
    twitter_entrypoint_prompt = Column(
        String,
        nullable=True,
        comment="Extra prompt for twitter entrypoint",
    )
    twitter_config = Column(
        JSONB,
        nullable=True,
        comment="You must use your own key for twitter entrypoint, it is separated from twitter skills",
    )
    # twitter skills require config, but not require twitter_enabled flag.
    # As long as twitter_skills is not empty, the corresponding skills will be loaded.
    twitter_skills = Column(
        ARRAY(String),
        nullable=True,
        comment="List of Twitter-specific skills available to this agent",
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
        JSONB,
        nullable=True,
        comment="Telegram integration configuration settings",
    )
    # telegram skills not used for now
    telegram_skills = Column(
        ARRAY(String),
        nullable=True,
        comment="List of Telegram-specific skills available to this agent",
    )
    # skills have no category
    common_skills = Column(
        ARRAY(String),
        nullable=True,
        comment="List of general-purpose skills available to this agent",
    )
    # if enso_enabled, the enso skillset will be enabled, enso_config will be checked
    enso_enabled = Column(
        Boolean,
        nullable=True,
        default=False,
        comment="Whether Enso integration is enabled",
    )
    # enso skills
    enso_skills = Column(
        ARRAY(String),
        nullable=True,
        comment="List of Enso-specific skills available to this agent",
    )
    enso_config = Column(
        JSONB,
        nullable=True,
        comment="Enso integration configuration settings",
    )
    # Acolyt skills
    acolyt_skills = Column(
        ARRAY(String),
        nullable=True,
        comment="List of Acolyt-specific skills available to this agent",
    )
    acolyt_config = Column(
        JSONB,
        nullable=True,
        comment="Acolyt integration configuration settings",
    )
    # Allora skills
    allora_skills = Column(
        ARRAY(String),
        nullable=True,
        comment="List of Allora-specific skills available to this agent",
    )
    allora_config = Column(
        JSONB,
        nullable=True,
        comment="Allora integration configuration settings",
    )
    # ELFA skills
    elfa_skills = Column(
        ARRAY(String),
        nullable=True,
        comment="List of Elfa-specific skills available to this agent",
    )
    elfa_config = Column(
        JSONB,
        nullable=True,
        comment="Elfa integration configuration settings",
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
        Literal[
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4.1-nano",
            "gpt-4.1-mini",
            "gpt-4.1",
            "o4-mini",
            "deepseek-chat",
            "deepseek-reasoner",
            "grok-2",
            "grok-3",
            "grok-3-mini",
            "eternalai",
            "reigent",
        ],
        PydanticField(
            default="gpt-4.1-nano",
            description="AI model identifier to be used by this agent for processing requests. Available models: gpt-4o, gpt-4o-mini, deepseek-chat, deepseek-reasoner, grok-2, eternalai, reigent",
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
        Optional[Literal["cdp"]],
        PydanticField(
            default="cdp",
            description="Provider of the agent's wallet",
            json_schema_extra={
                "x-group": "onchain",
            },
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
    # if cdp_enabled, agent will have a cdp wallet
    cdp_enabled: Annotated[
        Optional[bool],
        PydanticField(
            default=False,
            description="Whether CDP (Coinbase Development Platform) integration is enabled",
            json_schema_extra={
                "x-group": "deprecated",
            },
        ),
    ]
    cdp_skills: Annotated[
        Optional[List[str]],
        PydanticField(
            default=None,
            deprecated="Please use skills instead",
            description="List of CDP skills available to this agent",
            json_schema_extra={
                "x-group": "deprecated",
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
    # if goat_enabled, will load goat skills
    crossmint_config: Annotated[
        Optional[dict],
        PydanticField(
            default=None,
            description="Dict of Crossmint wallet configurations",
            json_schema_extra={
                "x-group": "experimental",
            },
        ),
    ]
    goat_enabled: Annotated[
        Optional[bool],
        PydanticField(
            default=False,
            description="Whether GOAT integration is enabled",
            json_schema_extra={
                "x-group": "experimental",
            },
        ),
    ]
    goat_skills: Annotated[
        Optional[dict],
        PydanticField(
            default=None,
            description="Dict of GOAT skills and their corresponding configurations",
            json_schema_extra={
                "x-group": "experimental",
            },
        ),
    ]
    # if twitter_enabled, the twitter_entrypoint will be enabled, twitter_config will be checked
    twitter_entrypoint_enabled: Annotated[
        Optional[bool],
        PydanticField(
            default=False,
            description="Dangerous, reply all mentions from x.com",
            json_schema_extra={
                "x-group": "entrypoint",
            },
        ),
    ]
    twitter_entrypoint_prompt: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Extra prompt for twitter entrypoint",
            max_length=10000,
            json_schema_extra={
                "x-group": "entrypoint",
            },
        ),
    ]
    twitter_config: Annotated[
        Optional[dict],
        PydanticField(
            default=None,
            description="You must use your own key for twitter entrypoint, it is separated from twitter skills",
            json_schema_extra={
                "x-group": "entrypoint",
            },
        ),
    ]
    # twitter skills require config, but not require twitter_enabled flag.
    # As long as twitter_skills is not empty, the corresponding skills will be loaded.
    twitter_skills: Annotated[
        Optional[List[str]],
        PydanticField(
            default=None,
            deprecated="Please use skills instead",
            description="List of Twitter-specific skills available to this agent",
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
    # telegram skills not used for now
    telegram_skills: Annotated[
        Optional[List[str]],
        PydanticField(
            default=None,
            deprecated="Please use skills instead",
            description="List of Telegram-specific skills available to this agent",
            json_schema_extra={
                "x-group": "deprecated",
            },
        ),
    ]
    # skills have no category
    common_skills: Annotated[
        Optional[List[str]],
        PydanticField(
            default=None,
            deprecated="Please use skills instead",
            description="List of general-purpose skills available to this agent",
            json_schema_extra={
                "x-group": "deprecated",
            },
        ),
    ]
    # if enso_enabled, the enso skillset will be enabled, enso_config will be checked
    enso_enabled: Annotated[
        Optional[bool],
        PydanticField(
            default=False,
            deprecated="Please use skills instead",
            description="Whether Enso integration is enabled",
            json_schema_extra={
                "x-group": "deprecated",
            },
        ),
    ]
    # enso skills
    enso_skills: Annotated[
        Optional[List[str]],
        PydanticField(
            default=None,
            deprecated="Please use skills instead",
            description="List of Enso-specific skills available to this agent",
            json_schema_extra={
                "x-group": "deprecated",
            },
        ),
    ]
    enso_config: Annotated[
        Optional[dict],
        PydanticField(
            default=None,
            deprecated="Please use skills instead",
            description="Enso integration configuration settings",
            json_schema_extra={
                "x-group": "deprecated",
            },
        ),
    ]
    # Acolyt skills
    acolyt_skills: Annotated[
        Optional[List[str]],
        PydanticField(
            default=None,
            deprecated="Please use skills instead",
            description="List of Acolyt-specific skills available to this agent",
            json_schema_extra={
                "x-group": "deprecated",
            },
        ),
    ]
    acolyt_config: Annotated[
        Optional[dict],
        PydanticField(
            default=None,
            deprecated="Please use skills instead",
            description="Acolyt integration configuration settings",
            json_schema_extra={
                "x-group": "deprecated",
            },
        ),
    ]
    # Allora skills
    allora_skills: Annotated[
        Optional[List[str]],
        PydanticField(
            default=None,
            deprecated="Please use skills instead",
            description="List of Allora-specific skills available to this agent",
            json_schema_extra={
                "x-group": "deprecated",
            },
        ),
    ]
    allora_config: Annotated[
        Optional[dict],
        PydanticField(
            default=None,
            deprecated="Please use skills instead",
            description="Allora integration configuration settings",
            json_schema_extra={
                "x-group": "deprecated",
            },
        ),
    ]
    # ELFA skills
    elfa_skills: Annotated[
        Optional[List[str]],
        PydanticField(
            default=None,
            deprecated="Please use skills instead",
            description="List of Elfa-specific skills available to this agent",
            json_schema_extra={
                "x-group": "deprecated",
            },
        ),
    ]
    elfa_config: Annotated[
        Optional[dict],
        PydanticField(
            default=None,
            deprecated="Please use skills instead",
            description="Elfa integration configuration settings",
            json_schema_extra={
                "x-group": "deprecated",
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

        for config in self.autonomous:
            # Check that exactly one scheduling method is provided
            if not config.minutes and not config.cron:
                raise HTTPException(
                    status_code=400, detail="either minutes or cron must have a value"
                )

            if config.minutes and config.cron:
                raise HTTPException(
                    status_code=400, detail="only one of minutes or cron can be set"
                )

            # Validate minimum interval of 5 minutes
            if config.minutes and config.minutes < 5:
                raise HTTPException(
                    status_code=400,
                    detail="The shortest execution interval is 5 minutes",
                )

            # Validate cron expression to ensure interval is at least 5 minutes
            if config.cron:
                # First validate the cron expression format using cron-validator

                try:
                    CronValidator.parse(config.cron)
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid cron expression format: {config.cron}",
                    )

                parts = config.cron.split()
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
            if self.owner and db_agent.owner != self.owner:
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

    # auto increment number by db
    number: Annotated[
        int,
        PydanticField(
            description="Auto-incrementing number assigned by the system for easy reference",
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

    def has_image_parser_skill(self) -> bool:
        if self.skills:
            for skill, skill_config in self.skills.items():
                if skill == "openai" and skill_config.get("enabled"):
                    states = skill_config.get("states", {})
                    if states.get("image_to_text") in ["public", "private"]:
                        return True
                    if states.get("gpt_image_to_image") in ["public", "private"]:
                        return True
        return False

    def is_model_support_image(self) -> bool:
        return self.model in ["gpt-4o"]

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
    # auto increment number by db
    number: Annotated[
        int,
        PydanticField(
            description="Auto-incrementing number assigned by the system for easy reference",
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
    # skills
    skills: Annotated[
        Optional[Dict[str, Any]],
        PydanticField(
            default=None,
            description="Dict of skills and their corresponding configurations",
        ),
    ]
    wallet_provider: Annotated[
        Optional[Literal["cdp"]],
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
        PydanticField(description="Whether the agent accepts image inputs"),
    ]

    def etag(self) -> str:
        """Generate an ETag for this agent response.

        The ETag is based on a hash of the entire object to ensure it changes
        whenever any part of the agent is modified.

        Returns:
            str: ETag value for the agent
        """
        import hashlib
        import json

        # Generate hash from the entire object data using json mode to handle datetime objects
        # Sort keys to ensure consistent ordering of dictionary keys
        data = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return f"{hashlib.md5(data.encode()).hexdigest()}"

    @classmethod
    def from_agent(
        cls, agent: Agent, agent_data: Optional["AgentData"] = None
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
                        if "states" in skill_config:
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
        cdp_wallet_address = None
        if agent_data and agent_data.cdp_wallet_data:
            try:
                wallet_data = json.loads(agent_data.cdp_wallet_data)
                cdp_wallet_address = wallet_data.get("default_address_id")
            except (json.JSONDecodeError, AttributeError):
                pass

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
            agent.is_model_support_image() or agent.has_image_parser_skill()
        )

        # Add processed fields to response
        data.update(
            {
                "cdp_wallet_address": cdp_wallet_address,
                "has_twitter_linked": has_twitter_linked,
                "linked_twitter_username": linked_twitter_username,
                "linked_twitter_name": linked_twitter_name,
                "has_twitter_self_key": has_twitter_self_key,
                "has_telegram_self_key": has_telegram_self_key,
                "linked_telegram_username": linked_telegram_username,
                "linked_telegram_name": linked_telegram_name,
                "accept_image_input": accept_image_input,
            }
        )

        return cls.model_validate(data)


class AgentDataTable(Base):
    """Agent data model for database storage of additional data related to the agent."""

    __tablename__ = "agent_data"

    id = Column(String, primary_key=True, comment="Same as Agent.id")
    cdp_wallet_data = Column(String, nullable=True, comment="CDP wallet data")
    crossmint_wallet_data = Column(
        JSONB, nullable=True, comment="Crossmint wallet information"
    )
    twitter_id = Column(String, nullable=True, comment="Twitter user ID")
    twitter_username = Column(String, nullable=True, comment="Twitter username")
    twitter_name = Column(String, nullable=True, comment="Twitter display name")
    twitter_access_token = Column(String, nullable=True, comment="Twitter access token")
    twitter_access_token_expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Twitter access token expiration time",
    )
    twitter_refresh_token = Column(
        String, nullable=True, comment="Twitter refresh token"
    )
    twitter_self_key_refreshed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Twitter self-key userinfo last refresh time",
    )
    telegram_id = Column(String, nullable=True, comment="Telegram user ID")
    telegram_username = Column(String, nullable=True, comment="Telegram username")
    telegram_name = Column(String, nullable=True, comment="Telegram display name")
    error_message = Column(String, nullable=True, comment="Last error message")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when the agent data was created",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Timestamp when the agent data was last updated",
    )


class AgentData(BaseModel):
    """Agent data model for storing additional data related to the agent."""

    model_config = ConfigDict(from_attributes=True)

    id: Annotated[
        str,
        PydanticField(
            description="Same as Agent.id",
        ),
    ]
    cdp_wallet_data: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="CDP wallet data",
        ),
    ]
    crossmint_wallet_data: Annotated[
        Optional[dict],
        PydanticField(
            default=None,
            description="Crossmint wallet information",
        ),
    ]
    twitter_id: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Twitter user ID",
        ),
    ]
    twitter_username: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Twitter username",
        ),
    ]
    twitter_name: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Twitter display name",
        ),
    ]
    twitter_access_token: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Twitter access token",
        ),
    ]
    twitter_access_token_expires_at: Annotated[
        Optional[datetime],
        PydanticField(
            default=None,
            description="Twitter access token expiration time",
        ),
    ]
    twitter_refresh_token: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Twitter refresh token",
        ),
    ]
    twitter_self_key_refreshed_at: Annotated[
        Optional[datetime],
        PydanticField(
            default=None,
            description="Twitter self-key userinfo last refresh time",
        ),
    ]
    telegram_id: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Telegram user ID",
        ),
    ]
    telegram_username: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Telegram username",
        ),
    ]
    telegram_name: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Telegram display name",
        ),
    ]
    error_message: Annotated[
        Optional[str],
        PydanticField(
            default=None,
            description="Last error message",
        ),
    ]
    created_at: Annotated[
        datetime,
        PydanticField(
            default_factory=lambda: datetime.now(timezone.utc),
            description="Timestamp when the agent data was created",
        ),
    ]
    updated_at: Annotated[
        datetime,
        PydanticField(
            default_factory=lambda: datetime.now(timezone.utc),
            description="Timestamp when the agent data was last updated",
        ),
    ]

    @classmethod
    async def get(cls, agent_id: str) -> Optional["AgentData"]:
        """Get agent data by ID.

        Args:
            agent_id: Agent ID

        Returns:
            AgentData if found, None otherwise

        Raises:
            HTTPException: If there are database errors
        """
        async with get_session() as db:
            item = await db.get(AgentDataTable, agent_id)
            if item:
                return cls.model_validate(item)
            return None

    async def save(self) -> None:
        """Save or update agent data.

        Raises:
            HTTPException: If there are database errors
        """
        async with get_session() as db:
            existing = await db.get(AgentDataTable, self.id)
            if existing:
                # Update existing record
                for field, value in self.model_dump(exclude_unset=True).items():
                    setattr(existing, field, value)
                db.add(existing)
            else:
                # Create new record
                db_agent_data = AgentDataTable(**self.model_dump())
                db.add(db_agent_data)

            await db.commit()

    @staticmethod
    async def patch(id: str, data: dict) -> "AgentData":
        """Update agent data.

        Args:
            id: ID of the agent
            data: Dictionary containing fields to update

        Returns:
            Updated agent data

        Raises:
            HTTPException: If there are database errors
        """
        async with get_session() as db:
            agent_data = await db.get(AgentDataTable, id)
            if not agent_data:
                agent_data = AgentDataTable(id=id, **data)
                db.add(agent_data)
            else:
                for key, value in data.items():
                    setattr(agent_data, key, value)
            await db.commit()
            await db.refresh(agent_data)
            return AgentData.model_validate(agent_data)


class AgentPluginDataTable(Base):
    """Database model for storing plugin-specific data for agents.

    This model uses a composite primary key of (agent_id, plugin, key) to store
    plugin-specific data for agents in a flexible way.

    Attributes:
        agent_id: ID of the agent this data belongs to
        plugin: Name of the plugin this data is for
        key: Key for this specific piece of data
        data: JSON data stored for this key
    """

    __tablename__ = "agent_plugin_data"

    agent_id = Column(String, primary_key=True)
    plugin = Column(String, primary_key=True)
    key = Column(String, primary_key=True)
    data = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AgentPluginData(BaseModel):
    """Model for storing plugin-specific data for agents.

    This model uses a composite primary key of (agent_id, plugin, key) to store
    plugin-specific data for agents in a flexible way.

    Attributes:
        agent_id: ID of the agent this data belongs to
        plugin: Name of the plugin this data is for
        key: Key for this specific piece of data
        data: JSON data stored for this key
    """

    model_config = ConfigDict(from_attributes=True)

    agent_id: Annotated[
        str,
        PydanticField(description="ID of the agent this data belongs to"),
    ]
    plugin: Annotated[
        str,
        PydanticField(description="Name of the plugin this data is for"),
    ]
    key: Annotated[
        str,
        PydanticField(description="Key for this specific piece of data"),
    ]
    data: Annotated[
        Dict[str, Any],
        PydanticField(default=None, description="JSON data stored for this key"),
    ]
    created_at: Annotated[
        datetime,
        PydanticField(
            description="Timestamp when this data was created",
            default_factory=lambda: datetime.now(timezone.utc),
        ),
    ]
    updated_at: Annotated[
        datetime,
        PydanticField(
            description="Timestamp when this data was last updated",
            default_factory=lambda: datetime.now(timezone.utc),
        ),
    ]

    @classmethod
    async def get(
        cls, agent_id: str, plugin: str, key: str
    ) -> Optional["AgentPluginData"]:
        """Get plugin data for an agent.

        Args:
            agent_id: ID of the agent
            plugin: Name of the plugin
            key: Data key

        Returns:
            AgentPluginData if found, None otherwise

        Raises:
            HTTPException: If there are database errors
        """
        async with get_session() as db:
            item = await db.scalar(
                select(AgentPluginDataTable).where(
                    AgentPluginDataTable.agent_id == agent_id,
                    AgentPluginDataTable.plugin == plugin,
                    AgentPluginDataTable.key == key,
                )
            )
            if item:
                return cls.model_validate(item)
            return None

    async def save(self) -> None:
        """Save or update plugin data.

        Raises:
            HTTPException: If there are database errors
        """
        async with get_session() as db:
            plugin_data = await db.scalar(
                select(AgentPluginDataTable).where(
                    AgentPluginDataTable.agent_id == self.agent_id,
                    AgentPluginDataTable.plugin == self.plugin,
                    AgentPluginDataTable.key == self.key,
                )
            )

            if plugin_data:
                # Update existing record
                plugin_data.data = self.data
                db.add(plugin_data)
            else:
                # Create new record
                plugin_data = AgentPluginDataTable(
                    agent_id=self.agent_id,
                    plugin=self.plugin,
                    key=self.key,
                    data=self.data,
                )
                db.add(plugin_data)

            await db.commit()
            await db.refresh(plugin_data)

            # Refresh the model with updated data
            self.model_validate(plugin_data)


class AgentQuotaTable(Base):
    """AgentQuota database table model."""

    __tablename__ = "agent_quotas"

    id = Column(String, primary_key=True)
    plan = Column(String, default="self-hosted")
    message_count_total = Column(BigInteger, default=0)
    message_limit_total = Column(BigInteger, default=99999999)
    message_count_monthly = Column(BigInteger, default=0)
    message_limit_monthly = Column(BigInteger, default=99999999)
    message_count_daily = Column(BigInteger, default=0)
    message_limit_daily = Column(BigInteger, default=99999999)
    last_message_time = Column(DateTime(timezone=True), default=None, nullable=True)
    autonomous_count_total = Column(BigInteger, default=0)
    autonomous_limit_total = Column(BigInteger, default=99999999)
    autonomous_count_monthly = Column(BigInteger, default=0)
    autonomous_limit_monthly = Column(BigInteger, default=99999999)
    last_autonomous_time = Column(DateTime(timezone=True), default=None, nullable=True)
    twitter_count_total = Column(BigInteger, default=0)
    twitter_limit_total = Column(BigInteger, default=99999999)
    twitter_count_monthly = Column(BigInteger, default=0)
    twitter_limit_monthly = Column(BigInteger, default=99999999)
    twitter_count_daily = Column(BigInteger, default=0)
    twitter_limit_daily = Column(BigInteger, default=99999999)
    last_twitter_time = Column(DateTime(timezone=True), default=None, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AgentQuota(BaseModel):
    """AgentQuota model."""

    model_config = ConfigDict(from_attributes=True)

    id: Annotated[
        str, PydanticField(description="ID of the agent this quota belongs to")
    ]
    plan: Annotated[
        str, PydanticField(default="self-hosted", description="Agent plan name")
    ]
    message_count_total: Annotated[
        int, PydanticField(default=0, description="Total message count")
    ]
    message_limit_total: Annotated[
        int, PydanticField(default=99999999, description="Total message limit")
    ]
    message_count_monthly: Annotated[
        int, PydanticField(default=0, description="Monthly message count")
    ]
    message_limit_monthly: Annotated[
        int, PydanticField(default=99999999, description="Monthly message limit")
    ]
    message_count_daily: Annotated[
        int, PydanticField(default=0, description="Daily message count")
    ]
    message_limit_daily: Annotated[
        int, PydanticField(default=99999999, description="Daily message limit")
    ]
    last_message_time: Annotated[
        Optional[datetime],
        PydanticField(default=None, description="Last message timestamp"),
    ]
    autonomous_count_total: Annotated[
        int, PydanticField(default=0, description="Total autonomous operations count")
    ]
    autonomous_limit_total: Annotated[
        int,
        PydanticField(
            default=99999999, description="Total autonomous operations limit"
        ),
    ]
    autonomous_count_monthly: Annotated[
        int, PydanticField(default=0, description="Monthly autonomous operations count")
    ]
    autonomous_limit_monthly: Annotated[
        int,
        PydanticField(
            default=99999999, description="Monthly autonomous operations limit"
        ),
    ]
    autonomous_count_daily: Annotated[
        int, PydanticField(default=0, description="Daily autonomous operations count")
    ]
    autonomous_limit_daily: Annotated[
        int,
        PydanticField(
            default=99999999, description="Daily autonomous operations limit"
        ),
    ]
    last_autonomous_time: Annotated[
        Optional[datetime],
        PydanticField(default=None, description="Last autonomous operation timestamp"),
    ]
    twitter_count_total: Annotated[
        int, PydanticField(default=0, description="Total Twitter operations count")
    ]
    twitter_limit_total: Annotated[
        int,
        PydanticField(default=99999999, description="Total Twitter operations limit"),
    ]
    twitter_count_monthly: Annotated[
        int, PydanticField(default=0, description="Monthly Twitter operations count")
    ]
    twitter_limit_monthly: Annotated[
        int,
        PydanticField(default=99999999, description="Monthly Twitter operations limit"),
    ]
    twitter_count_daily: Annotated[
        int, PydanticField(default=0, description="Daily Twitter operations count")
    ]
    twitter_limit_daily: Annotated[
        int,
        PydanticField(default=99999999, description="Daily Twitter operations limit"),
    ]
    last_twitter_time: Annotated[
        Optional[datetime],
        PydanticField(default=None, description="Last Twitter operation timestamp"),
    ]
    created_at: Annotated[
        datetime,
        PydanticField(
            description="Timestamp when this quota was created",
            default_factory=lambda: datetime.now(timezone.utc),
        ),
    ]
    updated_at: Annotated[
        datetime,
        PydanticField(
            description="Timestamp when this quota was last updated",
            default_factory=lambda: datetime.now(timezone.utc),
        ),
    ]

    @classmethod
    async def get(cls, agent_id: str) -> "AgentQuota":
        """Get agent quota by id, if not exists, create a new one.

        Args:
            agent_id: Agent ID

        Returns:
            AgentQuota: The agent's quota object

        Raises:
            HTTPException: If there are database errors
        """
        async with get_session() as db:
            quota_record = await db.get(AgentQuotaTable, agent_id)
            if not quota_record:
                # Create new record
                quota_record = AgentQuotaTable(
                    id=agent_id,
                )
                db.add(quota_record)
                await db.commit()
                await db.refresh(quota_record)

            return cls.model_validate(quota_record)

    def has_message_quota(self) -> bool:
        """Check if the agent has message quota.

        Returns:
            bool: True if the agent has quota, False otherwise
        """
        # Check total limit
        if self.message_count_total >= self.message_limit_total:
            return False
        # Check monthly limit
        if self.message_count_monthly >= self.message_limit_monthly:
            return False
        # Check daily limit
        if self.message_count_daily >= self.message_limit_daily:
            return False
        return True

    def has_autonomous_quota(self) -> bool:
        """Check if the agent has autonomous quota.

        Returns:
            bool: True if the agent has quota, False otherwise
        """
        # Check total limit
        if self.autonomous_count_total >= self.autonomous_limit_total:
            return False
        # Check monthly limit
        if self.autonomous_count_monthly >= self.autonomous_limit_monthly:
            return False
        return True

    def has_twitter_quota(self) -> bool:
        """Check if the agent has twitter quota.

        Returns:
            bool: True if the agent has quota, False otherwise
        """
        # Check total limit
        if self.twitter_count_total >= self.twitter_limit_total:
            return False
        # Check daily limit
        if self.twitter_count_daily >= self.twitter_limit_daily:
            return False
        return True

    async def add_message(self) -> None:
        """Add a message to the agent's message count."""
        async with get_session() as db:
            quota_record = await db.get(AgentQuotaTable, self.id)

            if quota_record:
                # Update record
                quota_record.message_count_total += 1
                quota_record.message_count_monthly += 1
                quota_record.message_count_daily += 1
                quota_record.last_message_time = datetime.now(timezone.utc)
                db.add(quota_record)
                await db.commit()

                # Update this instance
                await db.refresh(quota_record)
                self.message_count_total = quota_record.message_count_total
                self.message_count_monthly = quota_record.message_count_monthly
                self.message_count_daily = quota_record.message_count_daily
                self.last_message_time = quota_record.last_message_time
                self.updated_at = quota_record.updated_at

    async def add_autonomous(self) -> None:
        """Add an autonomous operation to the agent's autonomous count."""
        async with get_session() as db:
            quota_record = await db.get(AgentQuotaTable, self.id)
            if quota_record:
                # Update record
                quota_record.autonomous_count_total += 1
                quota_record.autonomous_count_monthly += 1
                quota_record.last_autonomous_time = datetime.now(timezone.utc)
                db.add(quota_record)
                await db.commit()

                # Update this instance
                await db.refresh(quota_record)
                self.model_validate(quota_record)

    async def add_twitter_message(self) -> None:
        """Add a twitter message to the agent's twitter count.

        Raises:
            HTTPException: If there are database errors
        """
        async with get_session() as db:
            quota_record = await db.get(AgentQuotaTable, self.id)

            if quota_record:
                # Update record
                quota_record.twitter_count_total += 1
                quota_record.twitter_count_daily += 1
                quota_record.last_twitter_time = datetime.now(timezone.utc)
                db.add(quota_record)
                await db.commit()

                # Update this instance
                await db.refresh(quota_record)
                self.model_validate(quota_record)
