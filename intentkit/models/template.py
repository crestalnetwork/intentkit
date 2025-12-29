"""Template models for agent templates."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import Field as PydanticField
from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.models.agent import AgentCore
from intentkit.models.base import Base


class TemplateTable(Base):
    """Template table db model."""

    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        comment="Unique identifier for the template",
    )
    owner: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Owner identifier of the template, used for access control",
    )
    team_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Team identifier of the template, used for access control",
    )
    description: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Description of the template",
    )

    # AgentCore fields
    name: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Display name of the template",
    )
    picture: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Avatar of the template",
    )
    purpose: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Purpose or role of the template",
    )
    personality: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Personality traits of the template",
    )
    principles: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Principles or values of the template",
    )
    model: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="gpt-5-mini",
        comment="LLM of the template",
    )
    prompt: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Base system prompt that defines the template's behavior and capabilities",
    )
    prompt_append: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Additional system prompt that has higher priority than the base prompt",
    )
    temperature: Mapped[float | None] = mapped_column(
        nullable=True,
        default=0.7,
        comment="The randomness of the generated results (0.0~2.0)",
    )
    frequency_penalty: Mapped[float | None] = mapped_column(
        nullable=True,
        default=0.0,
        comment="The frequency penalty (-2.0~2.0)",
    )
    presence_penalty: Mapped[float | None] = mapped_column(
        nullable=True,
        default=0.0,
        comment="The presence penalty (-2.0~2.0)",
    )
    short_term_memory_strategy: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        default="trim",
        comment="Strategy for managing short-term memory when context limit is reached",
    )
    wallet_provider: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Provider of the template's wallet",
    )
    network_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        default="base-mainnet",
        comment="Network identifier",
    )
    skills: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="Dict of skills and their corresponding configurations",
    )

    # auto timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when the template was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        comment="Timestamp when the template was last updated",
    )


class Template(AgentCore):
    """Template model that extends AgentCore with additional fields."""

    id: Annotated[
        str,
        PydanticField(
            description="Unique identifier for the template",
        ),
    ]
    owner: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Owner identifier of the template, used for access control",
        ),
    ]
    team_id: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Team identifier of the template, used for access control",
        ),
    ]
    description: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Description of the template",
        ),
    ]
    created_at: Annotated[
        datetime | None,
        PydanticField(
            default=None,
            description="Timestamp when the template was created",
        ),
    ]
    updated_at: Annotated[
        datetime | None,
        PydanticField(
            default=None,
            description="Timestamp when the template was last updated",
        ),
    ]
