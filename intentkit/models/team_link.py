"""Team links: external app accounts linked at the team level via Composio.

A "link" is one connected external account (e.g. a Gmail inbox, an X/Twitter
account) bound to a team. The linkable apps form a code-maintained whitelist
(``LINK_APPS``); a team may link the same app several times. Active links give
the team's lead agent MCP tools that act through the linked accounts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, ClassVar

from epyxid import XID
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from sqlalchemy import DateTime, Index, String, delete, func, select, update
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.config.base import Base
from intentkit.config.db import get_session


@dataclass(frozen=True)
class LinkAppDef:
    """One entry of the code-maintained whitelist of linkable apps."""

    app: str
    """Whitelist key used in APIs and stored on link rows, e.g. 'twitter'."""

    name: str
    """Human-readable name for UI and prompts."""

    description: str
    """Short description of what linking this app enables."""

    toolkit: str
    """Composio toolkit slug."""


# The whitelist of apps a team may link, keyed by app. Order matters: it is
# the display order in the UI and the system prompt.
LINK_APPS: dict[str, LinkAppDef] = {
    d.app: d
    for d in (
        LinkAppDef(
            app="twitter",
            name="Twitter / X",
            description="Post, search, and read tweets with the linked X account",
            toolkit="twitter",
        ),
        LinkAppDef(
            app="notion",
            name="Notion",
            description="Read and write pages and databases in the linked Notion workspace",
            toolkit="notion",
        ),
        LinkAppDef(
            app="gmail",
            name="Gmail",
            description="Read, search, and send email with the linked Gmail account",
            toolkit="gmail",
        ),
        LinkAppDef(
            app="supabase",
            name="Supabase",
            description="Manage projects, run SQL, and deploy functions in the linked Supabase account",
            toolkit="supabase",
        ),
    )
}

# Link lifecycle: rows are created "pending" when the OAuth flow starts and
# become "active" on completion. Later status syncs may downgrade them when
# Composio reports the account expired/revoked/inactive/failed.
LINK_STATUS_PENDING = "pending"
LINK_STATUS_ACTIVE = "active"


class TeamLinkTable(Base):
    """One linked (or in-flight) external app account of a team."""

    __tablename__: str = "team_links"
    __table_args__: Any = (
        Index("ix_team_links_team", "team_id"),
        # The OAuth completion callback carries only the connected account id;
        # unique so one Composio account can never map to two teams.
        Index("ix_team_links_connected_account", "connected_account_id", unique=True),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(XID())
    )
    team_id: Mapped[str] = mapped_column(String, nullable=False)
    app: Mapped[str] = mapped_column(String, nullable=False)
    connected_account_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=LINK_STATUS_PENDING
    )
    account_label: Mapped[str | None] = mapped_column(String, nullable=True)
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


class TeamLink(BaseModel):
    """Read model + persistence helpers for team links."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    id: Annotated[str, Field(description="Link ID")]
    team_id: Annotated[str, Field(description="Owning team ID")]
    app: Annotated[str, Field(description="Whitelist app key, e.g. 'gmail'")]
    connected_account_id: Annotated[
        str, Field(description="Composio connected account id (ca_...)")
    ]
    status: Annotated[
        str, Field(description="pending | active | expired | revoked | ...")
    ]
    account_label: Annotated[
        str | None,
        Field(default=None, description="Display label of the linked account"),
    ] = None
    created_by: Annotated[str, Field(description="User who initiated the link")]
    created_at: Annotated[datetime, Field(description="Creation timestamp")]
    updated_at: Annotated[datetime, Field(description="Last update timestamp")]

    @field_serializer("created_at", "updated_at")
    @classmethod
    def serialize_datetime(cls, v: datetime) -> str:
        return v.isoformat(timespec="milliseconds")

    @classmethod
    async def get(cls, link_id: str) -> TeamLink | None:
        async with get_session() as db:
            item = await db.get(TeamLinkTable, link_id)
            return cls.model_validate(item) if item else None

    @classmethod
    async def get_by_connected_account(cls, account_id: str) -> TeamLink | None:
        async with get_session() as db:
            stmt = select(TeamLinkTable).where(
                TeamLinkTable.connected_account_id == account_id
            )
            item = (await db.scalars(stmt)).first()
            return cls.model_validate(item) if item else None

    @classmethod
    async def list_for_team(
        cls, team_id: str, status: str | None = None
    ) -> list[TeamLink]:
        """List a team's links (oldest first), optionally filtered by status."""
        async with get_session() as db:
            stmt = select(TeamLinkTable).where(TeamLinkTable.team_id == team_id)
            if status is not None:
                stmt = stmt.where(TeamLinkTable.status == status)
            stmt = stmt.order_by(TeamLinkTable.created_at)
            result = await db.scalars(stmt)
            return [cls.model_validate(row) for row in result]

    @classmethod
    async def create(
        cls,
        team_id: str,
        app: str,
        connected_account_id: str,
        created_by: str,
    ) -> TeamLink:
        """Insert a new pending link row and return it."""
        async with get_session() as db:
            record = TeamLinkTable(
                team_id=team_id,
                app=app,
                connected_account_id=connected_account_id,
                status=LINK_STATUS_PENDING,
                created_by=created_by,
            )
            db.add(record)
            await db.commit()
            await db.refresh(record)
            return cls.model_validate(record)

    @classmethod
    async def set_status(
        cls, link_id: str, status: str, account_label: str | None = None
    ) -> TeamLink | None:
        """Update a link's status (and optionally its label). Returns the
        updated link, or None if the row disappeared."""
        async with get_session() as db:
            item = await db.get(TeamLinkTable, link_id)
            if not item:
                return None
            item.status = status
            if account_label is not None:
                item.account_label = account_label
            db.add(item)
            await db.commit()
            await db.refresh(item)
            return cls.model_validate(item)

    @classmethod
    async def set_statuses(cls, updates: dict[str, str]) -> None:
        """Update several links' statuses in one transaction (status sync)."""
        if not updates:
            return
        async with get_session() as db:
            for link_id, status in updates.items():
                await db.execute(
                    update(TeamLinkTable)
                    .where(TeamLinkTable.id == link_id)
                    .values(status=status)
                )
            await db.commit()

    @classmethod
    async def delete(cls, link_id: str) -> None:
        async with get_session() as db:
            await db.execute(delete(TeamLinkTable).where(TeamLinkTable.id == link_id))
            await db.commit()

    @classmethod
    async def delete_pending_for_app(cls, team_id: str, app: str) -> list[str]:
        """Drop leftover pending rows for a team+app; returns their connected
        account ids so the caller can also clean them up at Composio.

        Called when a new link attempt starts: any previous attempt for the
        same app that never completed is superseded (Composio expires the
        half-open account on its side after ~10 minutes).
        """
        async with get_session() as db:
            stmt = (
                delete(TeamLinkTable)
                .where(
                    TeamLinkTable.team_id == team_id,
                    TeamLinkTable.app == app,
                    TeamLinkTable.status == LINK_STATUS_PENDING,
                )
                .returning(TeamLinkTable.connected_account_id)
            )
            account_ids = list((await db.scalars(stmt)).all())
            await db.commit()
            return account_ids
