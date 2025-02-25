import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import yaml
from epyxid import XID
from fastapi import HTTPException
from pydantic import BaseModel
from pydantic.json_schema import SkipJsonSchema
from sqlalchemy import BigInteger, Column, DateTime, Identity, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlmodel import Field, SQLModel, select

from models.db import get_session
from models.skill import SkillConfig

logger = logging.getLogger(__name__)


class Agent(SQLModel, table=True):
    """Agent model."""

    __tablename__ = "agents"

    id: str = Field(
        primary_key=True,
        description="Unique identifier for the agent. Must be URL-safe, containing only lowercase letters, numbers, and hyphens",
    )
    number: SkipJsonSchema[int] = Field(
        sa_column=Column(BigInteger, Identity(start=1, increment=1), nullable=False),
        description="Auto-incrementing number assigned by the system for easy reference",
    )
    name: Optional[str] = Field(default=None, description="Display name of the agent")
    slug: Optional[str] = Field(
        default=None,
        description="Slug of the agent, used for URL generation",
    )
    ticker: Optional[str] = Field(
        default=None,
        description="Ticker symbol of the agent",
    )
    token_address: Optional[str] = Field(
        default=None,
        description="Token address of the agent",
    )
    purpose: Optional[str] = Field(
        default=None,
        description="Purpose or role of the agent",
    )
    personality: Optional[str] = Field(
        default=None,
        description="Personality traits of the agent",
    )
    principles: Optional[str] = Field(
        default=None,
        description="Principles or values of the agent",
    )
    owner: Optional[str] = Field(
        default=None,
        description="Owner identifier of the agent, used for access control",
    )
    upstream_id: Optional[str] = Field(
        default=None, description="External reference ID for idempotent operations"
    )
    # AI part
    model: Optional[str] = Field(
        default="gpt-4o-mini",
        description="AI model identifier to be used by this agent for processing requests. Available models: gpt-4o, gpt-4o-mini, chatgpt-4o-latest, deepseek-chat, deepseek-reasoner, grok-2",
    )
    prompt: Optional[str] = Field(
        default=None,
        description="Base system prompt that defines the agent's behavior and capabilities",
    )
    prompt_append: Optional[str] = Field(
        default=None,
        description="Additional system prompt that has higher priority than the base prompt",
    )
    temperature: Optional[float] = Field(
        default=0.7,
        description="AI model temperature parameter controlling response randomness (0.0~1.0)",
    )
    frequency_penalty: Optional[float] = Field(
        default=0.0,
        description="Frequency penalty for the AI model, a higher value penalizes new tokens based on their existing frequency in the chat history (-2.0~2.0)",
    )
    presence_penalty: Optional[float] = Field(
        default=0.0,
        description="Presence penalty for the AI model, a higher value penalizes new tokens based on whether they appear in the chat history (-2.0~2.0)",
    )
    # autonomous mode
    autonomous_enabled: Optional[bool] = Field(
        default=False,
        description="Whether the agent can operate autonomously without user input",
    )
    autonomous_minutes: Optional[int] = Field(
        default=240,
        description="Interval in minutes between autonomous operations when enabled",
    )
    autonomous_prompt: Optional[str] = Field(
        default=None, description="Special prompt used during autonomous operation mode"
    )
    # if cdp_enabled, agent will have a cdp wallet
    cdp_enabled: Optional[bool] = Field(
        default=False,
        description="Whether CDP (Crestal Development Platform) integration is enabled",
    )
    cdp_skills: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(ARRAY(String)),
        description="List of CDP skills available to this agent",
    )
    cdp_network_id: Optional[str] = Field(
        default="base-mainnet", description="Network identifier for CDP integration"
    )
    # if goat_enabled, will load goat skills
    crossmint_config: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="Dict of Crossmint wallet configurations",
    )
    goat_enabled: Optional[bool] = Field(
        default=False,
        description="Whether GOAT integration is enabled",
    )
    goat_skills: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="Dict of GOAT skills and their corresponding configurations",
    )
    # if twitter_enabled, the twitter_entrypoint will be enabled, twitter_config will be checked
    twitter_entrypoint_enabled: Optional[bool] = Field(
        default=False, description="Whether the agent can receive events from Twitter"
    )
    twitter_config: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="Twitter integration configuration settings",
    )
    # twitter skills require config, but not require twitter_enabled flag.
    # As long as twitter_skills is not empty, the corresponding skills will be loaded.
    twitter_skills: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(ARRAY(String)),
        description="List of Twitter-specific skills available to this agent",
    )
    # if telegram_entrypoint_enabled, the telegram_entrypoint_enabled will be enabled, telegram_config will be checked
    telegram_entrypoint_enabled: Optional[bool] = Field(
        default=False, description="Whether the agent can receive events from Telegram"
    )
    telegram_config: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="Telegram integration configuration settings",
    )
    # telegram skills not used for now
    telegram_skills: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(ARRAY(String)),
        description="List of Telegram-specific skills available to this agent",
    )
    # skills
    skills: Optional[Dict[str, SkillConfig]] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="Dict of skills and their corresponding configurations",
    )
    # skills have no category
    common_skills: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(ARRAY(String)),
        description="List of general-purpose skills available to this agent",
    )
    # if enso_enabled, the enso skillset will be enabled, enso_config will be checked
    enso_enabled: Optional[bool] = Field(
        default=False, description="Whether Enso integration is enabled"
    )
    # enso skills
    enso_skills: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(ARRAY(String)),
        description="List of Enso-specific skills available to this agent",
    )
    enso_config: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="Enso integration configuration settings",
    )
    # Acolyt skills
    acolyt_skills: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(ARRAY(String)),
        description="List of Acolyt-specific skills available to this agent",
    )
    acolyt_config: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="Acolyt integration configuration settings",
    )
    # Allora skills
    allora_skills: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(ARRAY(String)),
        description="List of Allora-specific skills available to this agent",
    )
    allora_config: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="Allora integration configuration settings",
    )
    # ELFA skills
    elfa_skills: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(ARRAY(String)),
        description="List of Elfa-specific skills available to this agent",
    )
    elfa_config: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="Elfa integration configuration settings",
    )
    # auto timestamp
    created_at: SkipJsonSchema[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"server_default": func.now()},
        nullable=False,
    )
    updated_at: SkipJsonSchema[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "onupdate": lambda: datetime.now(timezone.utc),
        },
        nullable=False,
    )

    def to_yaml(self) -> str:
        """
        Dump the agent model to YAML format with field descriptions as comments.
        The comments are extracted from the field descriptions in the model.
        Fields annotated with SkipJsonSchema will be excluded from the output.

        Returns:
            str: YAML representation of the agent with field descriptions as comments
        """
        data = {}
        yaml_lines = []

        for field_name, field in self.model_fields.items():
            logger.debug(f"Processing field {field_name} with type {field.metadata}")
            # Skip fields with SkipJsonSchema annotation
            if any(isinstance(item, SkipJsonSchema) for item in field.metadata):
                continue

            value = getattr(self, field_name)
            data[field_name] = value
            # Add comment from field description if available
            description = field.description
            if description:
                if len(yaml_lines) > 0:  # Add blank line between fields
                    yaml_lines.append("")
                # Split description into multiple lines if too long
                desc_lines = [f"# {line}" for line in description.split("\n")]
                yaml_lines.extend(desc_lines)

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
            else:
                # Handle non-string values
                yaml_value = yaml.dump(
                    {field_name: value},
                    default_flow_style=False,
                    allow_unicode=True,
                )
                yaml_lines.append(yaml_value.rstrip())

        return "\n".join(yaml_lines) + "\n"

    @classmethod
    async def count(cls) -> int:
        async with get_session() as db:
            return (await db.exec(select(func.count(Agent.id)))).one()

    @classmethod
    async def get(cls, agent_id: str) -> "Agent | None":
        async with get_session() as db:
            return (await db.exec(select(Agent).where(Agent.id == agent_id))).first()

    async def create_or_update(self) -> ("Agent", bool):
        """Create the agent if not exists, otherwise update it.

        Returns:
            Agent: The created or updated agent

        Raises:
            HTTPException: If there are permission or validation errors
            SQLAlchemyError: If there are database errors
        """
        try:
            # Generate ID if not provided
            if not self.id:
                self.id = str(XID())

            # input check
            self.number = None
            self.created_at = None
            self.updated_at = None

            # Check for markdown headers in text fields
            fields_to_check = [
                "purpose",
                "personality",
                "principles",
                "prompt",
                "prompt_append",
            ]
            for field in fields_to_check:
                value = getattr(self, field)
                if value and isinstance(value, str):
                    for line_num, line in enumerate(value.split("\n"), 1):
                        line = line.strip()
                        if line.startswith("# ") or line.startswith("## "):
                            raise HTTPException(
                                status_code=400,
                                detail=f"Field '{field}' contains markdown level 1/2 header at line {line_num}. You can use level 3 (### ) instead.",
                            )

            if not all(c.islower() or c.isdigit() or c == "-" for c in self.id):
                raise HTTPException(
                    status_code=400,
                    detail="Agent ID must contain only lowercase letters, numbers, and hyphens.",
                )

            # Check if agent exists
            existing_agent = await self.__class__.get(self.id)
            if existing_agent:
                # Check owner
                if (
                    existing_agent.owner
                    and self.owner  # if no owner, the request is coming from internal call, so skip the check
                    and existing_agent.owner != self.owner
                ):
                    raise HTTPException(
                        status_code=403,
                        detail="Your JWT token does not match the agent owner",
                    )
                # Check upstream_id
                if (
                    existing_agent.upstream_id
                    and self.upstream_id
                    and existing_agent.upstream_id != self.upstream_id
                ):
                    raise HTTPException(
                        status_code=400,
                        detail="upstream_id cannot be changed after creation",
                    )
                # Update existing agent
                for field in self.model_fields:
                    if field != "id":  # Skip the primary key
                        if getattr(self, field) is not None:
                            setattr(existing_agent, field, getattr(self, field))
                async with get_session() as db:
                    db.add(existing_agent)
                    await db.commit()
                    await db.refresh(existing_agent)
                return existing_agent, False
            else:
                # Check upstream_id for idempotent
                async with get_session() as db:
                    if self.upstream_id:
                        upstream_match = (
                            await db.exec(
                                select(Agent).where(
                                    Agent.upstream_id == self.upstream_id
                                )
                            )
                        ).first()
                        if upstream_match:
                            raise HTTPException(
                                status_code=400,
                                detail="upstream_id already exists",
                            )
                    # Create new agent
                    db.add(self)
                    await db.commit()
                    await db.refresh(self)
                return self, True
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Database error: {str(e)}",
            ) from e


class AgentResponse(BaseModel):
    """Response model for Agent API."""

    # config part
    id: str = Field(
        description="Unique identifier for the agent. Must be URL-safe, containing only lowercase letters, numbers, and hyphens"
    )
    number: int = Field(
        description="Auto-incrementing number assigned by the system for easy reference"
    )
    name: Optional[str] = Field(default=None, description="Display name of the agent")
    slug: Optional[str] = Field(
        default=None,
        description="Slug of the agent, used for URL generation",
    )
    ticker: Optional[str] = Field(
        default=None,
        description="Ticker symbol of the agent",
    )
    token_address: Optional[str] = Field(
        default=None,
        description="Token address of the agent",
    )
    purpose: Optional[str] = Field(
        default=None,
        description="Purpose or role of the agent",
    )
    personality: Optional[str] = Field(
        default=None,
        description="Personality traits of the agent",
    )
    principles: Optional[str] = Field(
        default=None,
        description="Principles or values of the agent",
    )
    owner: Optional[str] = Field(
        default=None,
        description="Owner identifier of the agent, used for access control",
    )
    upstream_id: Optional[str] = Field(
        default=None, description="External reference ID for idempotent operations"
    )
    model: str = Field(
        description="AI model identifier to be used by this agent for processing requests"
    )
    prompt: Optional[str] = Field(
        default=None,
        description="Base system prompt that defines the agent's behavior and capabilities",
    )
    prompt_append: Optional[str] = Field(
        default=None,
        description="Additional system prompt that overrides or extends the base prompt",
    )
    temperature: float = Field(
        description="AI model temperature parameter controlling response randomness (0.0-1.0)"
    )
    frequency_penalty: Optional[float] = Field(
        default=0.0,
        description="Frequency penalty for the AI model, a higher value penalizes new tokens based on their existing frequency in the chat history (-2.0~2.0)",
    )
    presence_penalty: Optional[float] = Field(
        default=0.0,
        description="Presence penalty for the AI model, a higher value penalizes new tokens based on whether they appear in the chat history (-2.0~2.0)",
    )
    autonomous_enabled: bool = Field(
        description="Whether the agent can operate autonomously without user input"
    )
    autonomous_minutes: Optional[int] = Field(
        description="Interval in minutes between autonomous operations when enabled"
    )
    autonomous_prompt: Optional[str] = Field(
        description="Special prompt used during autonomous operation mode"
    )
    cdp_enabled: bool = Field(
        description="Whether CDP (Crestal Development Platform) integration is enabled"
    )
    cdp_skills: Optional[List[str]] = Field(
        description="List of CDP skills available to this agent"
    )
    cdp_network_id: Optional[str] = Field(
        description="Network identifier for CDP integration"
    )
    crossmint_config: Optional[dict] = Field(
        description="Dict of Crossmint wallet configurations",
    )
    goat_enabled: Optional[bool] = Field(
        default=False,
        description="Whether GOAT integration is enabled",
    )
    goat_skills: Optional[dict] = Field(
        description="Dict of GOAT skills and their corresponding configurations",
    )
    twitter_entrypoint_enabled: bool = Field(
        description="Whether the agent can receive events from Twitter"
    )
    twitter_config: Optional[dict] = Field(
        description="Twitter integration configuration settings",
    )
    twitter_skills: Optional[List[str]] = Field(
        description="List of Twitter-specific skills available to this agent"
    )
    telegram_entrypoint_enabled: bool = Field(
        description="Whether the agent can receive events from Telegram"
    )
    telegram_config: Optional[dict] = Field(
        description="Telegram integration configuration settings",
    )
    telegram_skills: Optional[List[str]] = Field(
        description="List of Telegram-specific skills available to this agent"
    )
    common_skills: Optional[List[str]] = Field(
        description="List of general-purpose skills available to this agent"
    )
    enso_enabled: bool = Field(description="Whether Enso integration is enabled")
    enso_skills: Optional[List[str]] = Field(
        description="List of Enso-specific skills available to this agent",
    )
    enso_config: Optional[dict] = Field(
        description="Enso integration configuration settings",
    )
    acolyt_skills: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(ARRAY(String)),
        description="List of Acolyt-specific skills available to this agent",
    )
    acolyt_config: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="Acolyt integration configuration settings",
    )
    allora_skills: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(ARRAY(String)),
        description="List of Allora-specific skills available to this agent",
    )
    allora_config: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="Allora integration configuration settings",
    )
    skills: Optional[Dict[str, SkillConfig]] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="Dict of skills and their corresponding configurations",
    )
    created_at: datetime | None = Field(
        description="Timestamp when this agent was created"
    )
    updated_at: datetime | None = Field(
        description="Timestamp when this agent was last updated"
    )

    # data part
    cdp_wallet_address: Optional[str] = Field(
        description="CDP wallet address for the agent"
    )
    has_twitter_linked: bool = Field(
        description="Whether the agent has linked their Twitter account"
    )
    linked_twitter_username: Optional[str] = Field(
        description="The username of the linked Twitter account"
    )
    linked_twitter_name: Optional[str] = Field(
        description="The name of the linked Twitter account"
    )
    has_twitter_self_key: bool = Field(
        description="Whether the agent has self-keyed their Twitter account"
    )
    has_telegram_self_key: bool = Field(
        description="Whether the agent has self-keyed their Telegram account"
    )
    linked_telegram_username: Optional[str] = Field(
        description="The username of the linked Telegram account"
    )
    linked_telegram_name: Optional[str] = Field(
        description="The name of the linked Telegram account"
    )

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

        # Process Twitter self-key status and remove sensitive fields
        has_twitter_self_key = False
        twitter_config = data.get("twitter_config", {})
        if twitter_config:
            required_keys = {
                "access_token",
                "bearer_token",
                "consumer_key",
                "consumer_secret",
                "access_token_secret",
            }
            has_twitter_self_key = all(
                key in twitter_config and twitter_config[key] for key in required_keys
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
            }
        )

        return cls(**data)


class AgentData(SQLModel, table=True):
    """Agent data model for storing additional data related to the agent."""

    __tablename__ = "agent_data"

    id: str = Field(primary_key=True)  # Same as Agent.id
    cdp_wallet_data: Optional[str]
    crossmint_wallet_data: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="Crossmint wallet information",
    )
    twitter_id: Optional[str]
    twitter_username: Optional[str]
    twitter_name: Optional[str]
    twitter_access_token: Optional[str]
    twitter_access_token_expires_at: Optional[datetime] = Field(
        sa_type=DateTime(timezone=True)
    )
    twitter_refresh_token: Optional[str]
    telegram_id: Optional[str]
    telegram_username: Optional[str]
    telegram_name: Optional[str]
    error_message: Optional[str]
    created_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"server_default": func.now()},
        nullable=False,
    )
    updated_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "onupdate": lambda: datetime.now(timezone.utc),
        },
        nullable=False,
    )

    @classmethod
    async def get(cls, agent_id: str) -> Optional["AgentData"]:
        """Get agent data by ID.

        Args:
            id: Agent ID
            db: Database session

        Returns:
            AgentData if found, None otherwise

        Raises:
            HTTPException: If there are database errors
        """
        try:
            async with get_session() as db:
                return (await db.exec(select(cls).where(cls.id == agent_id))).first()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get agent data: {str(e)}",
            ) from e

    async def save(self) -> None:
        """Save or update agent data.

        Args:
            db: Database session

        Raises:
            HTTPException: If there are database errors
        """
        try:
            async with get_session() as db:
                existing = (
                    await db.exec(
                        select(self.__class__).where(self.__class__.id == self.id)
                    )
                ).first()

                if existing:
                    # Update existing record
                    for field in self.model_fields:
                        if getattr(self, field) is not None:
                            setattr(existing, field, getattr(self, field))
                    db.add(existing)
                else:
                    # Create new record
                    db.add(self)

                await db.commit()
                await db.refresh(self if not existing else existing)
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save agent data: {str(e)}",
            ) from e


class AgentQuota(SQLModel, table=True):
    """AgentQuota model."""

    __tablename__ = "agent_quotas"

    id: str = Field(primary_key=True)
    plan: str = Field(default="self-hosted")
    message_count_total: int = Field(default=0)
    message_limit_total: int = Field(default=99999999)
    message_count_monthly: int = Field(default=0)
    message_limit_monthly: int = Field(default=99999999)
    message_count_daily: int = Field(default=0)
    message_limit_daily: int = Field(default=99999999)
    last_message_time: Optional[datetime] = Field(default=None)
    autonomous_count_total: int = Field(default=0)
    autonomous_limit_total: int = Field(default=99999999)
    autonomous_count_monthly: int = Field(default=0)
    autonomous_limit_monthly: int = Field(default=99999999)
    last_autonomous_time: Optional[datetime] = Field(default=None)
    twitter_count_total: int = Field(default=0)
    twitter_limit_total: int = Field(default=99999999)
    twitter_count_daily: int = Field(default=0)
    twitter_limit_daily: int = Field(default=99999999)
    last_twitter_time: Optional[datetime] = Field(default=None)
    created_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"server_default": func.now()},
        nullable=False,
    )
    updated_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "onupdate": lambda: datetime.now(timezone.utc),
        },
        nullable=False,
    )

    @classmethod
    async def get(cls, agent_id: str) -> "AgentQuota":
        """Get agent quota by id, if not exists, create a new one.

        Args:
            agent_id: Agent ID
            db: Database session

        Returns:
            AgentQuota: The agent's quota object

        Raises:
            HTTPException: If there are database errors
        """
        try:
            async with get_session() as db:
                quota = (await db.exec(select(cls).where(cls.id == agent_id))).first()
                if not quota:
                    quota = cls(id=agent_id)
                    db.add(quota)
                    await db.commit()
                    await db.refresh(quota)
            return quota
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get agent quota: {str(e)}",
            ) from e

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
        """Add a message to the agent's message count.

        Args:
            db: Database session

        Raises:
            HTTPException: If there are database errors
        """
        try:
            async with get_session() as db:
                self.message_count_total += 1
                self.message_count_monthly += 1
                self.message_count_daily += 1
                self.last_message_time = datetime.now()
                db.add(self)
                await db.commit()
                await db.refresh(self)
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to add message: {str(e)}",
            ) from e

    async def add_autonomous(self) -> None:
        """Add an autonomous message to the agent's autonomous count.

        Args:
            db: Database session

        Raises:
            HTTPException: If there are database errors
        """
        try:
            async with get_session() as db:
                self.autonomous_count_total += 1
                self.autonomous_count_monthly += 1
                self.last_autonomous_time = datetime.now()
                db.add(self)
                await db.commit()
                await db.refresh(self)
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to add autonomous message: {str(e)}",
            ) from e

    async def add_twitter(self) -> None:
        """Add a twitter message to the agent's twitter count.

        Args:
            db: Database session

        Raises:
            HTTPException: If there are database errors
        """
        try:
            async with get_session() as db:
                self.twitter_count_total += 1
                self.twitter_count_daily += 1
                self.last_twitter_time = datetime.now()
                db.add(self)
                await db.commit()
                await db.refresh(self)
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to add twitter message: {str(e)}",
            ) from e


class AgentPluginData(SQLModel, table=True):
    """Model for storing plugin-specific data for agents.

    This model uses a composite primary key of (agent_id, plugin, key) to store
    plugin-specific data for agents in a flexible way.

    Attributes:
        agent_id: ID of the agent this data belongs to
        plugin: Name of the plugin this data is for
        key: Key for this specific piece of data
        data: JSON data stored for this key
    """

    __tablename__ = "agent_plugin_data"

    agent_id: str = Field(primary_key=True)
    plugin: str = Field(primary_key=True)
    key: str = Field(primary_key=True)
    data: Dict[str, Any] = Field(sa_column=Column(JSONB, nullable=True))
    created_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"server_default": func.now()},
        nullable=False,
    )
    updated_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "onupdate": lambda: datetime.now(timezone.utc),
        },
        nullable=False,
    )

    @classmethod
    async def get(
        cls, agent_id: str, plugin: str, key: str
    ) -> Optional["AgentPluginData"]:
        """Get plugin data for an agent.

        Args:
            agent_id: ID of the agent
            plugin: Name of the plugin
            key: Data key
            db: Database session

        Returns:
            AgentPluginData if found, None otherwise

        Raises:
            HTTPException: If there are database errors
        """
        try:
            async with get_session() as db:
                return (
                    await db.exec(
                        select(cls).where(
                            cls.agent_id == agent_id,
                            cls.plugin == plugin,
                            cls.key == key,
                        )
                    )
                ).first()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get plugin data: {str(e)}",
            ) from e

    async def save(self) -> None:
        """Save or update plugin data.

        Args:
            db: Database session

        Raises:
            HTTPException: If there are database errors
        """
        try:
            async with get_session() as db:
                existing = (
                    await db.exec(
                        select(AgentPluginData).where(
                            AgentPluginData.agent_id == self.agent_id,
                            AgentPluginData.plugin == self.plugin,
                            AgentPluginData.key == self.key,
                        )
                    )
                ).first()

                if existing:
                    # Update existing record
                    existing.data = self.data
                    db.add(existing)
                else:
                    # Create new record
                    db.add(self)

                await db.commit()
                await db.refresh(self if not existing else existing)
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save plugin data: {str(e)}",
            ) from e
