"""Share link model: grants time-limited public read access to a chat or post."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, ClassVar

from epyxid import XID
from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField
from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.config.base import Base
from intentkit.models.agent_post import AgentPost
from intentkit.models.chat import ChatMessage


class ShareLinkTargetType(str, Enum):
    """Type of entity a share link points to."""

    CHAT = "chat"
    POST = "post"


class ShareLinkBase(BaseModel):
    """Base fields for a share link."""

    target_type: Annotated[
        ShareLinkTargetType,
        PydanticField(description="Type of the shared target"),
    ]
    target_id: Annotated[
        str,
        PydanticField(description="ID of the shared target", max_length=40),
    ]
    agent_id: Annotated[
        str,
        PydanticField(
            description="ID of the agent associated with the target",
            max_length=20,
        ),
    ]
    user_id: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="User who created the link; None for agent-initiated links",
        ),
    ] = None
    team_id: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Team in which the link was created; None for agent-initiated links",
        ),
    ] = None
    expires_at: Annotated[
        datetime,
        PydanticField(description="Timestamp when this share link expires"),
    ]


class ShareLinkCreate(ShareLinkBase):
    """Input model for creating a share link."""

    pass


class ShareLink(ShareLinkBase):
    """Full share link model with generated fields."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    id: Annotated[
        str, PydanticField(description="Unique identifier for the share link")
    ]
    view_count: Annotated[
        int,
        PydanticField(
            default=0,
            description="Number of times the share link has been viewed",
        ),
    ] = 0
    created_at: Annotated[
        datetime,
        PydanticField(description="Timestamp when the share link was created"),
    ]


class SharedPostView(BaseModel):
    """Public view of a shared post."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    post: AgentPost


class SharedChatInfo(BaseModel):
    """Public-safe projection of a chat: no owner user_id, no internal counters."""

    id: Annotated[str, PydanticField(description="Chat ID")]
    agent_id: Annotated[str, PydanticField(description="Agent ID")]
    summary: Annotated[str, PydanticField(description="Chat summary / title")]
    created_at: Annotated[
        datetime, PydanticField(description="Chat creation timestamp")
    ]
    updated_at: Annotated[
        datetime, PydanticField(description="Chat last-update timestamp")
    ]


class SharedChatView(BaseModel):
    """Public view of a shared chat with its visible messages."""

    chat: SharedChatInfo
    messages: list[ChatMessage]


class ShareLinkView(BaseModel):
    """Public response for resolving a share link."""

    id: str
    target_type: ShareLinkTargetType
    expires_at: datetime
    post: SharedPostView | None = None
    chat: SharedChatView | None = None


class ShareLinkTable(Base):
    """SQLAlchemy model for ShareLink."""

    __tablename__: str = "share_links"
    __table_args__ = (
        Index(
            "ix_share_links_target",
            "target_type",
            "target_id",
            "agent_id",
            "expires_at",
        ),
        Index("ix_share_links_expires_at", "expires_at"),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(XID()),
        comment="Unique identifier for the share link",
    )
    target_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="Type of the shared target (chat or post)",
    )
    target_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="ID of the shared target",
    )
    agent_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="ID of the agent associated with the target",
    )
    user_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="User who created the link; NULL for agent-initiated links",
    )
    team_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Team in which the link was created; NULL for agent-initiated links",
    )
    view_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Number of times the share link has been viewed via the public API",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when the share link was created",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Timestamp when the share link expires",
    )
