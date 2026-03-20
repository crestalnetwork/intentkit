from __future__ import annotations

import secrets
from datetime import UTC, datetime
from enum import Enum
from typing import Annotated, Any, ClassVar

from epyxid import XID
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from sqlalchemy import DateTime, Index, Integer, String, func, select
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.config.base import Base
from intentkit.config.db import get_session


class TeamRole(str, Enum):
    """Role of a user in a team."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class TeamMemberTable(Base):
    """Team member database table model."""

    __tablename__: str = "team_members"
    __table_args__: Any = (Index("ix_team_members_user_team", "user_id", "team_id"),)

    team_id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )
    role: Mapped[TeamRole] = mapped_column(
        String,
        nullable=False,
        default=TeamRole.MEMBER,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TeamTable(Base):
    """Team database table model."""

    __tablename__: str = "teams"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    avatar: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
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


class TeamInviteTable(Base):
    """Team invite database table model."""

    __tablename__: str = "team_invites"
    __table_args__: Any = (Index("ix_team_invites_team_id", "team_id"),)

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(XID()),
    )
    team_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    code: Mapped[str] = mapped_column(
        String,
        nullable=False,
        unique=True,
        default=lambda: secrets.token_urlsafe(9),
    )
    invited_by: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    role: Mapped[TeamRole] = mapped_column(
        String,
        nullable=False,
        default=TeamRole.MEMBER,
    )
    max_uses: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    use_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TeamCreate(BaseModel):
    """Team creation model."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    id: Annotated[
        str,
        Field(
            description="Unique identifier for the team",
            min_length=2,
            max_length=60,
            pattern=r"^[a-z]([a-z0-9-]*[a-z0-9])?$",
        ),
    ]
    name: Annotated[
        str,
        Field(
            description="Name of the team",
            min_length=1,
            max_length=100,
        ),
    ]
    avatar: Annotated[
        str | None,
        Field(
            default=None,
            description="Avatar URL of the team",
        ),
    ]

    async def save(self, creator_user_id: str) -> "Team":
        """Create a new team and add the creator as owner.

        Args:
            creator_user_id: ID of the user creating the team

        Returns:
            Team: The created team
        """
        async with get_session() as db:
            # Create team
            team_record = TeamTable(**self.model_dump())
            db.add(team_record)

            # Add creator as owner
            member_record = TeamMemberTable(
                team_id=team_record.id,
                user_id=creator_user_id,
                role=TeamRole.OWNER,
            )
            db.add(member_record)

            await db.commit()
            await db.refresh(team_record)
            return Team.model_validate(team_record)


class Team(TeamCreate):
    """Team model with all fields."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        from_attributes=True,
    )

    created_at: Annotated[
        datetime, Field(description="Timestamp when this team was created")
    ]
    updated_at: Annotated[
        datetime, Field(description="Timestamp when this team was last updated")
    ]

    @field_serializer("created_at", "updated_at")
    @classmethod
    def serialize_datetime(cls, v: datetime) -> str:
        return v.isoformat(timespec="milliseconds")

    @classmethod
    async def get(cls, team_id: str) -> "Team | None":
        """Get a team by ID."""
        async with get_session() as db:
            team = await db.get(TeamTable, team_id)
            if team:
                return cls.model_validate(team)
            return None

    @classmethod
    async def get_owner(cls, team_id: str) -> str | None:
        """Get the owner user_id of a team.

        Each team has exactly one owner.
        Returns None if the team has no owner.
        """
        async with get_session() as db:
            stmt = select(TeamMemberTable.user_id).where(
                TeamMemberTable.team_id == team_id,
                TeamMemberTable.role == TeamRole.OWNER,
            )
            return await db.scalar(stmt)

    @classmethod
    async def get_by_user(cls, user_id: str) -> list["Team"]:
        """Get all teams a user belongs to."""
        async with get_session() as db:
            stmt = (
                select(TeamTable)
                .join(
                    TeamMemberTable,
                    TeamMemberTable.team_id == TeamTable.id,
                )
                .where(TeamMemberTable.user_id == user_id)
                .order_by(TeamTable.name)
            )
            result = await db.scalars(stmt)
            return [cls.model_validate(team) for team in result]


class TeamInvite(BaseModel):
    """Team invite model."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    id: str
    team_id: str
    code: str
    invited_by: str
    role: TeamRole
    max_uses: int | None
    use_count: int
    expires_at: datetime | None
    created_at: datetime

    @field_serializer("expires_at", "created_at")
    @classmethod
    def serialize_datetime(cls, v: datetime | None) -> str | None:
        if v is None:
            return None
        return v.isoformat(timespec="milliseconds")
