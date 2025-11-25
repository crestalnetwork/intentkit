from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Annotated

from epyxid import XID
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, Index, String, func, select
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.models.base import Base
from intentkit.models.db import get_session


class TeamRole(str, Enum):
    """Role of a user in a team."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class TeamMemberTable(Base):
    """Team member database table model."""

    __tablename__ = "team_members"
    __table_args__ = (
        Index("ix_team_members_team_user", "team_id", "user_id", unique=True),
        Index("ix_team_members_user_team", "user_id", "team_id"),
    )

    team_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("teams.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
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

    __tablename__ = "teams"

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


class TeamCreate(BaseModel):
    """Team creation model."""

    model_config = ConfigDict(from_attributes=True)

    id: Annotated[
        str,
        Field(
            default_factory=lambda: str(XID()),
            description="Unique identifier for the team",
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

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat(timespec="milliseconds")},
    )

    created_at: Annotated[
        datetime, Field(description="Timestamp when this team was created")
    ]
    updated_at: Annotated[
        datetime, Field(description="Timestamp when this team was last updated")
    ]

    @classmethod
    async def get(cls, team_id: str) -> "Team | None":
        """Get a team by ID.

        Args:
            team_id: ID of the team to get

        Returns:
            Team or None if not found
        """
        async with get_session() as db:
            team = await db.get(TeamTable, team_id)
            if team:
                return cls.model_validate(team)
            return None

    @classmethod
    async def get_by_user(cls, user_id: str) -> list["Team"]:
        """Get all teams a user belongs to.

        Args:
            user_id: ID of the user

        Returns:
            List of teams
        """
        async with get_session() as db:
            stmt = (
                select(TeamTable)
                .join(TeamMemberTable)
                .where(TeamMemberTable.user_id == user_id)
                .order_by(TeamTable.name)
            )
            result = await db.scalars(stmt)
            return [cls.model_validate(team) for team in result]
