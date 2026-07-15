"""Template models for agent templates."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, ClassVar

from pydantic import ConfigDict
from pydantic import Field as PydanticField
from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.config.base import Base
from intentkit.models.agent import AgentCore
from intentkit.models.llm_picker import pick_default_model


class TemplateTable(Base):
    """Template table db model."""

    __tablename__: str = "templates"

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
    model: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=pick_default_model,
        comment="LLM of the template",
    )
    reasoning_effort: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Reasoning/thinking effort (none/minimal/low/medium/high/xhigh/max); NULL follows the model default.",
    )
    system_prompt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="System prompt that defines the template's purpose, personality, principles, and behavior",
    )
    tools: Mapped[list[str] | None] = mapped_column(
        JSONB(),
        nullable=True,
        comment="List of enabled tool names",
    )
    search_internet: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, comment="Enable LLM native internet search"
    )
    enable_activity: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="Enable activity tools (create activity, recent activities)",
    )
    enable_post: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="Enable post tools (create post, get post, recent posts)",
    )
    sub_agents: Mapped[list[str] | None] = mapped_column(
        JSONB(),
        nullable=True,
        comment="List of sub-agent IDs or slugs that this agent can call",
    )
    sub_agent_prompt: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Additional instructions for how to use sub-agents",
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

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

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
