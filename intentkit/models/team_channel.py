from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_serializer
from sqlalchemy import Boolean, DateTime, Index, String, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.config.base import Base
from intentkit.config.db import get_session


class TeamChannelTable(Base):
    """Team channel configuration table."""

    __tablename__: str = "team_channels"

    team_id: Mapped[str] = mapped_column(String, primary_key=True)
    channel_type: Mapped[str] = mapped_column(String, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict[str, object] | None] = mapped_column(JSONB(), nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )


class TeamChannelDataTable(Base):
    """Runtime data for team channel bots.

    Platform-specific data is stored in the JSONB `data` column.
    JSONB supports GIN indexes for future reverse-lookup needs.
    """

    __tablename__: str = "team_channel_data"

    team_id: Mapped[str] = mapped_column(String, primary_key=True)
    channel_type: Mapped[str] = mapped_column(String, primary_key=True)
    data: Mapped[dict[str, object] | None] = mapped_column(JSONB(), nullable=True)


class TeamChannelChatTable(Base):
    """Binding of an external chat to a team for a centralized (shared) bot.

    When one official bot serves many teams (the team-side telegram/lark/slack
    channels), inbound events carry only the chat id — not the team. The bot
    resolves the owning team via this table. PK (channel_type, chat_id) backs
    that lookup; the secondary index lists a team's bound chats.
    """

    __tablename__: str = "team_channel_chats"
    __table_args__: Any = (
        Index("ix_team_channel_chats_team", "team_id", "channel_type"),
    )

    channel_type: Mapped[str] = mapped_column(String, primary_key=True)
    chat_id: Mapped[str] = mapped_column(String, primary_key=True)
    team_id: Mapped[str] = mapped_column(String, nullable=False)
    chat_name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TelegramChannelConfig(BaseModel):
    """Validation model for Telegram channel config."""

    token: str


class TelegramWhitelistEntry(BaseModel):
    """A single verified chat in the Telegram whitelist."""

    chat_id: str
    chat_name: str | None = None
    verified_at: str


class TelegramChannelData(BaseModel):
    """Typed runtime data for a Telegram channel bot."""

    bot_id: str | None = None
    bot_username: str | None = None
    bot_name: str | None = None
    status: str | None = None  # "listening" | "error" | "pending"
    status_message: str | None = None
    verification_code: str | None = None
    whitelist: list[TelegramWhitelistEntry] = []


class TelegramStatus(BaseModel):
    """Response model for Telegram channel status endpoint."""

    status: str | None = None
    verification_code: str | None = None
    bot_username: str | None = None
    bot_name: str | None = None
    whitelist: list[TelegramWhitelistEntry] = []

    @classmethod
    def from_data(cls, d: dict[str, object]) -> TelegramStatus:
        """Parse team_channel_data JSONB dict into a TelegramStatus."""
        try:
            parsed = TelegramChannelData.model_validate(d)
            return cls(
                status=parsed.status,
                verification_code=parsed.verification_code,
                bot_username=parsed.bot_username,
                bot_name=parsed.bot_name,
                whitelist=parsed.whitelist,
            )
        except Exception:
            return cls()


class WechatChannelConfig(BaseModel):
    """Validation model for WeChat channel config."""

    bot_token: str
    baseurl: str
    ilink_bot_id: str
    user_id: str


class WechatChannelData(BaseModel):
    """Typed runtime data for a WeChat channel bot."""

    bot_id: str | None = None
    bot_name: str | None = None
    typing_ticket: str | None = None
    context_token: str | None = None


class LarkChannelConfig(BaseModel):
    """Per-team Lark/Feishu install state, written by the OAuth callback.

    The team authorizes the single ISV (store) app for its own enterprise; the
    callback stores the enterprise's ``tenant_key`` here. Inbound events are
    routed to the team by ``tenant_key``; replies use the app's per-tenant
    access token (managed by the Go webhook service).
    """

    tenant_key: str
    tenant_name: str | None = None


class SlackChannelConfig(BaseModel):
    """Per-team Slack install state, written by the OAuth callback.

    The team installs the single distributed Slack app into its own workspace
    ("Add to Slack"); the callback stores the workspace id and that workspace's
    bot token here. Inbound events are routed to the team by ``workspace_id``;
    replies use ``bot_token``.
    """

    workspace_id: str
    bot_token: str
    workspace_name: str | None = None
    bot_user_id: str | None = None


class TeamChannel(BaseModel):
    """Read model for team channels."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    team_id: Annotated[str, Field(description="Team ID")]
    channel_type: Annotated[
        str, Field(description="Channel type (telegram, discord, etc.)")
    ]
    enabled: Annotated[
        bool, Field(default=True, description="Whether the channel is enabled")
    ] = True
    config: Annotated[
        dict[str, object] | None,
        Field(default=None, description="Platform-specific config"),
    ] = None
    owner_id: Annotated[
        str | None, Field(default=None, description="IntentKit user_id")
    ] = None
    created_by: Annotated[str, Field(description="Who set this up")]
    created_at: Annotated[datetime, Field(description="Creation timestamp")]
    updated_at: Annotated[datetime, Field(description="Last update timestamp")]

    @field_serializer("created_at", "updated_at")
    @classmethod
    def serialize_datetime(cls, v: datetime) -> str:
        return v.isoformat(timespec="milliseconds")

    @classmethod
    async def get(cls, team_id: str, channel_type: str) -> TeamChannel | None:
        """Get a specific team channel."""
        async with get_session() as db:
            item = await db.get(
                TeamChannelTable, {"team_id": team_id, "channel_type": channel_type}
            )
            if item:
                return cls.model_validate(item)
            return None

    async def save(self) -> None:
        """Save or update a team channel."""
        async with get_session() as db:
            existing = await db.get(
                TeamChannelTable,
                {"team_id": self.team_id, "channel_type": self.channel_type},
            )
            if existing:
                for field, value in self.model_dump(exclude_unset=True).items():
                    setattr(existing, field, value)
                db.add(existing)
            else:
                record = TeamChannelTable(**self.model_dump())
                db.add(record)
            await db.commit()

    @classmethod
    async def get_by_team(cls, team_id: str) -> list[TeamChannel]:
        """Get all channels for a team."""
        async with get_session() as db:
            stmt = select(TeamChannelTable).where(TeamChannelTable.team_id == team_id)
            result = await db.scalars(stmt)
            return [cls.model_validate(row) for row in result]


class TeamChannelData(BaseModel):
    """Read model for team channel runtime data."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    team_id: Annotated[str, Field(description="Team ID")]
    channel_type: Annotated[str, Field(description="Channel type")]
    data: Annotated[
        dict[str, object] | None,
        Field(default=None, description="Platform-specific runtime data"),
    ]

    @classmethod
    async def get(cls, team_id: str, channel_type: str) -> TeamChannelData | None:
        """Get team channel data."""
        async with get_session() as db:
            item = await db.get(
                TeamChannelDataTable,
                {"team_id": team_id, "channel_type": channel_type},
            )
            if item:
                return cls.model_validate(item)
            return None

    async def save(self) -> None:
        """Save or update team channel data."""
        async with get_session() as db:
            existing = await db.get(
                TeamChannelDataTable,
                {"team_id": self.team_id, "channel_type": self.channel_type},
            )
            if existing:
                existing.data = self.data
                db.add(existing)
            else:
                record = TeamChannelDataTable(**self.model_dump())
                db.add(record)
            await db.commit()


class TeamChannelChat(BaseModel):
    """Read model + helpers for chat→team bindings used by centralized bots."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    channel_type: Annotated[str, Field(description="Channel type")]
    chat_id: Annotated[str, Field(description="External chat id")]
    team_id: Annotated[str, Field(description="Owning team id")]
    chat_name: Annotated[str | None, Field(default=None, description="Chat title")] = (
        None
    )

    @classmethod
    async def get_team(cls, channel_type: str, chat_id: str) -> str | None:
        """Return the team_id that owns this chat, or None if unbound."""
        async with get_session() as db:
            item = await db.get(
                TeamChannelChatTable,
                {"channel_type": channel_type, "chat_id": chat_id},
            )
            return item.team_id if item else None

    @classmethod
    async def bind(
        cls,
        channel_type: str,
        chat_id: str,
        team_id: str,
        chat_name: str | None = None,
    ) -> None:
        """Bind (or rebind) a chat to a team. Atomic upsert, so two concurrent
        binds of the same chat can't race into a primary-key conflict."""
        stmt = (
            pg_insert(TeamChannelChatTable)
            .values(
                channel_type=channel_type,
                chat_id=chat_id,
                team_id=team_id,
                chat_name=chat_name,
            )
            .on_conflict_do_update(
                index_elements=["channel_type", "chat_id"],
                set_={"team_id": team_id, "chat_name": chat_name},
            )
        )
        async with get_session() as db:
            await db.execute(stmt)
            await db.commit()

    @classmethod
    async def list_for_team(
        cls, team_id: str, channel_type: str
    ) -> list[TeamChannelChat]:
        """List all chats bound to a team for a channel."""
        async with get_session() as db:
            stmt = select(TeamChannelChatTable).where(
                TeamChannelChatTable.team_id == team_id,
                TeamChannelChatTable.channel_type == channel_type,
            )
            result = await db.scalars(stmt)
            return [cls.model_validate(row) for row in result]

    @classmethod
    async def unbind(cls, channel_type: str, chat_id: str) -> bool:
        """Remove a chat binding. Returns True if a row was deleted."""
        async with get_session() as db:
            item = await db.get(
                TeamChannelChatTable,
                {"channel_type": channel_type, "chat_id": chat_id},
            )
            if item:
                await db.delete(item)
                await db.commit()
                return True
            return False
