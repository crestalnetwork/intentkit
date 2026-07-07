"""Team links: external app accounts linked via Composio.

A "link" is one connected external account (e.g. a Gmail inbox, an X/Twitter
account) bound to a team. The linkable apps form a code-maintained whitelist
(``LINK_APPS``); a team may link the same app several times. Active links give
the team's lead agent MCP tools that act through the linked accounts.

Each app has a level:

- ``team``: linked once by a team admin, shared by every member.
- ``user``: linked by each member for themselves; the lead agent only sees the
  accounts of the user it is currently talking to.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, ClassVar

from epyxid import XID
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from sqlalchemy import DateTime, Index, String, delete, func, or_, select, update
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.config.base import Base
from intentkit.config.db import get_session

# Link levels: who an account belongs to and who may manage it.
LINK_LEVEL_TEAM = "team"
LINK_LEVEL_USER = "user"


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

    level: str
    """LINK_LEVEL_TEAM (shared, admin-managed) or LINK_LEVEL_USER (per user)."""

    categories: tuple[str, ...]
    """Composio marketplace categories, used as UI filter tags."""


# The whitelist of apps that may be linked, keyed by app. Order matters: it is
# the display order in the UI and the system prompt (user-level apps first).
# Category names follow the Composio toolkit marketplace taxonomy.
LINK_APPS: dict[str, LinkAppDef] = {
    d.app: d
    for d in (
        # --- User-level apps: each member links their own account. ---
        LinkAppDef(
            app="gmail",
            name="Gmail",
            description="Read, search, and send email with the linked Gmail account",
            toolkit="gmail",
            level=LINK_LEVEL_USER,
            categories=("Collaboration & Communication",),
        ),
        LinkAppDef(
            app="outlook",
            name="Outlook",
            description="Read, send, and organize mail and calendar events in the linked Outlook account",
            toolkit="outlook",
            level=LINK_LEVEL_USER,
            categories=("Collaboration & Communication", "Scheduling & Booking"),
        ),
        LinkAppDef(
            app="googlecalendar",
            name="Google Calendar",
            description="View, create, and update events in the linked Google Calendar",
            toolkit="googlecalendar",
            level=LINK_LEVEL_USER,
            categories=("Scheduling & Booking",),
        ),
        LinkAppDef(
            app="linkedin",
            name="LinkedIn",
            description="Create posts and manage the linked LinkedIn profile",
            toolkit="linkedin",
            level=LINK_LEVEL_USER,
            categories=("Social Media",),
        ),
        # --- Team-level apps: linked by an admin, shared by the team. ---
        LinkAppDef(
            app="twitter",
            name="Twitter / X",
            description="Post, search, and read tweets with the linked X account",
            toolkit="twitter",
            level=LINK_LEVEL_TEAM,
            categories=("Social Media",),
        ),
        LinkAppDef(
            app="supabase",
            name="Supabase",
            description="Manage projects, run SQL, and deploy functions in the linked Supabase account",
            toolkit="supabase",
            level=LINK_LEVEL_TEAM,
            categories=("Developer Tools & DevOps",),
        ),
        LinkAppDef(
            app="notion",
            name="Notion",
            description="Read and write pages and databases in the linked Notion workspace",
            toolkit="notion",
            level=LINK_LEVEL_TEAM,
            categories=(
                "Productivity & Project Management",
                "Document & File Management",
            ),
        ),
        LinkAppDef(
            app="airtable",
            name="Airtable",
            description="Read and write records in the linked Airtable bases",
            toolkit="airtable",
            level=LINK_LEVEL_TEAM,
            categories=("Productivity & Project Management", "Data & Analytics"),
        ),
        LinkAppDef(
            app="googledocs",
            name="Google Docs",
            description="Create and edit documents in the linked Google Docs account",
            toolkit="googledocs",
            level=LINK_LEVEL_TEAM,
            categories=("Document & File Management",),
        ),
        LinkAppDef(
            app="googlesheets",
            name="Google Sheets",
            description="Read and write spreadsheets in the linked Google Sheets account",
            toolkit="googlesheets",
            level=LINK_LEVEL_TEAM,
            categories=("Document & File Management", "Data & Analytics"),
        ),
        LinkAppDef(
            app="googleslides",
            name="Google Slides",
            description="Create and edit presentations in the linked Google Slides account",
            toolkit="googleslides",
            level=LINK_LEVEL_TEAM,
            categories=("Document & File Management",),
        ),
        LinkAppDef(
            app="googledrive",
            name="Google Drive",
            description="Browse, upload, and manage files in the linked Google Drive",
            toolkit="googledrive",
            level=LINK_LEVEL_TEAM,
            categories=("Document & File Management",),
        ),
        LinkAppDef(
            app="linear",
            name="Linear",
            description="Create and manage issues and projects in the linked Linear workspace",
            toolkit="linear",
            level=LINK_LEVEL_TEAM,
            categories=("Productivity & Project Management",),
        ),
        LinkAppDef(
            app="github",
            name="GitHub",
            description="Manage repositories, issues, and pull requests with the linked GitHub account",
            toolkit="github",
            level=LINK_LEVEL_TEAM,
            categories=("Developer Tools & DevOps",),
        ),
        LinkAppDef(
            app="jira",
            name="Jira",
            description="Create and manage issues and boards in the linked Jira site",
            toolkit="jira",
            level=LINK_LEVEL_TEAM,
            categories=("Productivity & Project Management",),
        ),
        LinkAppDef(
            app="stripe",
            name="Stripe",
            description="Query customers, payments, and invoices in the linked Stripe account",
            toolkit="stripe",
            level=LINK_LEVEL_TEAM,
            categories=("Finance & Accounting",),
        ),
    )
}

# All whitelist categories in display order (the UI's filter tags).
LINK_CATEGORIES: tuple[str, ...] = tuple(
    dict.fromkeys(c for d in LINK_APPS.values() for c in d.categories)
)

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
    level: Mapped[str] = mapped_column(
        String, nullable=False, default=LINK_LEVEL_TEAM, server_default=LINK_LEVEL_TEAM
    )
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
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
    level: Annotated[
        str,
        Field(default=LINK_LEVEL_TEAM, description="Link level: 'team' or 'user'"),
    ] = LINK_LEVEL_TEAM
    user_id: Annotated[
        str | None,
        Field(
            default=None,
            description="Owning user for user-level links; None for team-level",
        ),
    ] = None
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
    async def list_for_team(cls, team_id: str) -> list[TeamLink]:
        """List ALL of a team's links (oldest first), every level and user.

        For maintenance paths like the Composio status sync; anything shown
        to a viewer must go through ``list_visible`` (or filter) instead.
        """
        async with get_session() as db:
            stmt = (
                select(TeamLinkTable)
                .where(TeamLinkTable.team_id == team_id)
                .order_by(TeamLinkTable.created_at)
            )
            result = await db.scalars(stmt)
            return [cls.model_validate(row) for row in result]

    @classmethod
    async def list_visible(
        cls, team_id: str, viewer_user_id: str | None, status: str | None = None
    ) -> list[TeamLink]:
        """List the links visible to one viewer (oldest first).

        Team-level links are visible to every member; user-level links only to
        their owning user. ``viewer_user_id=None`` returns team-level links
        only (used for user-agnostic contexts like the lead info endpoint).
        """
        async with get_session() as db:
            stmt = select(TeamLinkTable).where(TeamLinkTable.team_id == team_id)
            if viewer_user_id is None:
                stmt = stmt.where(TeamLinkTable.level == LINK_LEVEL_TEAM)
            else:
                stmt = stmt.where(
                    or_(
                        TeamLinkTable.level == LINK_LEVEL_TEAM,
                        TeamLinkTable.user_id == viewer_user_id,
                    )
                )
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
        level: str = LINK_LEVEL_TEAM,
        user_id: str | None = None,
    ) -> TeamLink:
        """Insert a new pending link row and return it.

        ``user_id`` is the owning user and must be set for user-level links;
        team-level links leave it None. list_visible and the unlink ownership
        check both rely on this pairing, so it is enforced here — the only
        write site.
        """
        if (level == LINK_LEVEL_USER) != (user_id is not None):
            raise ValueError(
                "user_id must be set for user-level links and None for team-level"
            )
        async with get_session() as db:
            record = TeamLinkTable(
                team_id=team_id,
                app=app,
                level=level,
                user_id=user_id,
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
    async def delete_pending_for_app(
        cls, team_id: str, app: str, user_id: str | None = None
    ) -> list[str]:
        """Drop leftover pending rows for a team+app; returns their connected
        account ids so the caller can also clean them up at Composio.

        Called when a new link attempt starts: any previous attempt for the
        same app that never completed is superseded (Composio expires the
        half-open account on its side after ~10 minutes). For user-level apps
        pass ``user_id`` so one user's new attempt never drops another user's
        in-flight attempt; without it only team-level rows match, so rows
        from before an app's level changed in the whitelist are never
        cross-deleted.
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
            if user_id is not None:
                stmt = stmt.where(TeamLinkTable.user_id == user_id)
            else:
                stmt = stmt.where(TeamLinkTable.level == LINK_LEVEL_TEAM)
            account_ids = list((await db.scalars(stmt)).all())
            await db.commit()
            return account_ids
