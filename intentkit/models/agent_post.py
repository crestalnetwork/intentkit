from __future__ import annotations

from datetime import datetime
from typing import Annotated

from epyxid import XID
from pydantic import BaseModel, ConfigDict, field_validator
from pydantic import Field as PydanticField
from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.config.base import Base


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
    agent_name: Annotated[
        str,
        PydanticField(
            description="Name of the agent who created the post",
            max_length=50,
        ),
    ]
    agent_picture: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Picture URL of the agent who created the post",
            max_length=1000,
        ),
    ] = None
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
    slug: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="URL slug for the post",
            max_length=60,
            pattern="^[a-zA-Z0-9-]+$",
        ),
    ] = None
    excerpt: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Short excerpt of the post",
            max_length=200,
        ),
    ] = None
    tags: Annotated[
        list[str],
        PydanticField(
            default_factory=list,
            description="List of tags",
            max_length=3,
        ),
    ]

    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_tags(cls, value: object) -> object:
        if value is None:
            return []
        return value


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
    agent_name: Annotated[
        str,
        PydanticField(
            description="Name of the agent who created the post",
        ),
    ]
    agent_picture: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Picture URL of the agent who created the post",
        ),
    ] = None
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

    slug: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="URL slug for the post",
        ),
    ]
    excerpt: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Short excerpt of the post",
        ),
    ]
    tags: Annotated[
        list[str],
        PydanticField(
            default_factory=list,
            description="List of tags",
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
        excerpt = table.excerpt
        if excerpt is None:
            excerpt = table.markdown[:500]
        return cls(
            id=table.id,
            agent_id=table.agent_id,
            agent_name=table.agent_name,
            agent_picture=table.agent_picture,
            title=table.title,
            cover=table.cover,
            slug=table.slug,
            excerpt=excerpt,
            tags=table.tags or [],
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
    agent_name: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="",
        comment="Name of the agent who created the post",
    )
    agent_picture: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Picture URL of the agent who created the post",
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
    slug: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="URL slug for the post",
    )
    excerpt: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Short excerpt of the post",
    )
    tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
        comment="List of tags",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when the post was created",
    )
