from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.config.base import Base


class AgentUserInputColumns:
    """Abstract base class containing columns that are common to AgentTable and other tables."""

    __abstract__: bool = True

    # Basic information fields from AgentCore
    name: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Display name of the agent",
    )
    picture: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Picture of the agent",
    )
    purpose: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Purpose or role of the agent",
    )
    personality: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Personality traits of the agent",
    )
    principles: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Principles or values of the agent",
    )

    # AI model configuration fields from AgentCore
    model: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        default="gpt-5-mini",
        comment="AI model identifier to be used by this agent for processing requests. Available models: gpt-4o, gpt-4o-mini, deepseek-chat, deepseek-reasoner, grok-2, eternalai",
    )
    prompt: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Base system prompt that defines the agent's behavior and capabilities",
    )
    prompt_append: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Additional system prompt that has higher priority than the base prompt",
    )
    temperature: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        default=0.7,
        comment="Controls response randomness (0.0~2.0). Higher values increase creativity but may reduce accuracy. For rigorous tasks, use lower values.",
    )
    frequency_penalty: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        default=0.0,
        comment="Controls repetition in responses (-2.0~2.0). Higher values reduce repetition, lower values allow more repetition.",
    )
    presence_penalty: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        default=0.0,
        comment="Controls topic adherence (-2.0~2.0). Higher values allow more topic deviation, lower values enforce stricter topic adherence.",
    )

    # Wallet and network configuration fields from AgentCore
    wallet_provider: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Provider of the agent's wallet",
    )
    readonly_wallet_address: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Readonly wallet address of the agent",
    )
    weekly_spending_limit: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Weekly spending limit in USDC when wallet_provider is safe",
    )
    network_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        default="base-mainnet",
        comment="Network identifier",
    )

    # Skills configuration from AgentCore
    skills: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Dict of skills and their corresponding configurations",
    )

    # Additional fields from AgentUserInput
    short_term_memory_strategy: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        default="trim",
        comment="Strategy for managing short-term memory when context limit is reached. 'trim' removes oldest messages, 'summarize' creates summaries.",
    )
    autonomous: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Autonomous agent configurations",
    )
    telegram_entrypoint_enabled: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        default=False,
        comment="Whether the agent can receive events from Telegram",
    )
    telegram_entrypoint_prompt: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Extra prompt for telegram entrypoint",
    )
    telegram_config: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Telegram integration configuration settings",
    )
    discord_entrypoint_enabled: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        default=False,
        comment="Whether the agent can receive events from Discord",
    )
    discord_config: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Discord integration configuration settings",
    )
    xmtp_entrypoint_prompt: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Extra prompt for xmtp entrypoint",
    )


class AgentTable(Base, AgentUserInputColumns):
    """Agent table db model."""

    __tablename__: str = "agents"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        comment="Unique identifier for the agent. Must be URL-safe, containing only lowercase letters, numbers, and hyphens",
    )
    slug: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Slug of the agent, used for URL generation",
    )
    owner: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Owner identifier of the agent, used for access control",
    )
    team_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Team identifier of the agent, used for access control",
    )
    template_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Template identifier of the agent",
    )
    extra_prompt: Mapped[str | None] = mapped_column(
        String(20000),
        nullable=True,
        comment="Only when the agent is created from a template.",
    )
    upstream_id: Mapped[str | None] = mapped_column(
        String,
        index=True,
        nullable=True,
        comment="Upstream reference ID for idempotent operations",
    )
    upstream_extra: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Additional data store for upstream use",
    )
    version: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Version hash of the agent",
    )
    statistics: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Statistics of the agent, update every 1 hour for query",
    )
    assets: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Assets of the agent, update every 1 hour for query",
    )
    account_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Account snapshot of the agent, update every 1 hour for query",
    )
    extra: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Other helper data fields for query, come from agent and agent data",
    )

    # Fields moved from AgentUserInputColumns that are no longer in AgentUserInput
    description: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Description of the agent, for public view, not contained in prompt",
    )
    external_website: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Link of external website of the agent, if you have one",
    )
    ticker: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Ticker symbol of the agent",
    )
    token_address: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Token address of the agent",
    )
    token_pool: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Pool of the agent token",
    )
    fee_percentage: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        nullable=True,
        comment="Fee percentage of the agent",
    )
    example_intro: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Introduction for example interactions",
    )
    examples: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="List of example interactions for the agent",
    )
    public_extra: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Public extra data of the agent",
    )
    deployed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the agent was deployed",
    )
    public_info_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the agent public info was last updated",
    )
    x402_price: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Price of the x402 request",
    )
    visibility: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Visibility level: 0=private, 10=team, 20=public",
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the agent was archived. NULL means not archived",
    )

    # auto timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when the agent was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        comment="Timestamp when the agent was last updated",
    )
