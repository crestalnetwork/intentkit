from __future__ import annotations

from datetime import datetime
from typing import Annotated

from epyxid import XID
from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.models.base import Base


class AgentPostBase(BaseModel):
    """Base model for AgentPost."""

    agent_id: Annotated[
        str,
        PydanticField(
            description="ID of the agent who created the post",
            min_length=1,
            max_length=20,
        ),
    ]
    title: Annotated[
        str,
        PydanticField(
            description="Title of the post",
            max_length=200,
        ),
    ]
    cover: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="URL of the cover image",
            max_length=1000,
        ),
    ]
    markdown: Annotated[
        str,
        PydanticField(
            description="Content of the post in markdown format",
        ),
    ]


class AgentPostCreate(AgentPostBase):
    """Model for creating an AgentPost."""

    pass


class AgentPost(AgentPostBase):
    """Model for a full AgentPost."""

    model_config = ConfigDict(from_attributes=True)

    id: Annotated[
        str,
        PydanticField(
            description="Unique identifier for the post",
        ),
    ]
    created_at: Annotated[
        datetime,
        PydanticField(
            description="Timestamp when the post was created",
        ),
    ]


class AgentPostBrief(BaseModel):
    """Brief model for AgentPost listing with truncated content."""

    model_config = ConfigDict(from_attributes=True)

    id: Annotated[
        str,
        PydanticField(
            description="Unique identifier for the post",
        ),
    ]
    agent_id: Annotated[
        str,
        PydanticField(
            description="ID of the agent who created the post",
        ),
    ]
    title: Annotated[
        str,
        PydanticField(
            description="Title of the post",
        ),
    ]
    cover: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="URL of the cover image",
        ),
    ]
    summary: Annotated[
        str,
        PydanticField(
            description="First 500 characters of post content",
        ),
    ]
    created_at: Annotated[
        datetime,
        PydanticField(
            description="Timestamp when the post was created",
        ),
    ]

    @classmethod
    def from_table(cls, table: "AgentPostTable") -> "AgentPostBrief":
        """Create a brief post from a table row, truncating markdown to 500 chars."""
        return cls(
            id=table.id,
            agent_id=table.agent_id,
            title=table.title,
            cover=table.cover,
            summary=table.markdown[:500]
            if len(table.markdown) > 500
            else table.markdown,
            created_at=table.created_at,
        )


class AgentPostTable(Base):
    """SQLAlchemy model for AgentPost."""

    __tablename__ = "agent_posts"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(XID()),
        comment="Unique identifier for the post",
    )
    agent_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
        comment="ID of the agent who created the post",
    )
    title: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="Title of the post",
    )
    cover: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="URL of the cover image",
    )
    markdown: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="Content of the post in markdown format",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when the post was created",
    )
