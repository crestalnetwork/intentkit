from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, ClassVar

from epyxid import XID
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_serializer,
    field_validator,
)
from sqlalchemy import DateTime, Index, Integer, String, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.config.base import Base
from intentkit.config.db import get_session


class TeamRole(str, Enum):
    """Role of a user in a team."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class TeamPlan(str, Enum):
    """Pricing plan tier for a team."""

    NONE = "none"
    FREE = "free"
    PRO = "pro"
    MAX = "max"


@dataclass(frozen=True)
class PlanConfig:
    """Configuration for a pricing plan tier."""

    name: str
    description: str
    free_quota: Decimal
    refill_amount: Decimal
    monthly_permanent_credits: Decimal
    seats: int
    month_price_cents: int
    year_price_cents: int


PLAN_CONFIGS: dict[TeamPlan, PlanConfig] = {
    TeamPlan.NONE: PlanConfig(
        name="No Plan",
        description="No active plan.",
        free_quota=Decimal("0"),
        refill_amount=Decimal("0"),
        monthly_permanent_credits=Decimal("0"),
        seats=1,
        month_price_cents=0,
        year_price_cents=0,
    ),
    TeamPlan.FREE: PlanConfig(
        name="Free",
        description=(
            "Basic plan with limited credits. "
            "Refills 10 credits/day. No monthly permanent credits."
        ),
        free_quota=Decimal("50"),
        refill_amount=Decimal("10"),
        monthly_permanent_credits=Decimal("0"),
        seats=1,
        month_price_cents=0,
        year_price_cents=0,
    ),
    TeamPlan.PRO: PlanConfig(
        name="Pro",
        description=(
            "Professional plan with enhanced credits. "
            "Refills 500 credits/day. 10,000 permanent credits/month."
        ),
        free_quota=Decimal("1000"),
        refill_amount=Decimal("500"),
        monthly_permanent_credits=Decimal("10000"),
        seats=3,
        month_price_cents=1900,
        year_price_cents=19000,
    ),
    TeamPlan.MAX: PlanConfig(
        name="Max",
        description=(
            "Maximum plan with full credits. "
            "Refills 5,000 credits/day. 100,000 permanent credits/month."
        ),
        free_quota=Decimal("10000"),
        refill_amount=Decimal("5000"),
        monthly_permanent_credits=Decimal("100000"),
        seats=15,
        month_price_cents=19900,
        year_price_cents=199000,
    ),
}


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
    default_channel: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    default_channel_chat_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    plan: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=TeamPlan.NONE.value,
        server_default=TeamPlan.NONE.value,
    )
    plan_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_credit_issue_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    lead_agent: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(),
        nullable=True,
        comment="Persisted lead agent config (name, avatar, personality)",
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


class TeamMember(BaseModel):
    """Team member info model."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    user_id: str
    team_id: str
    role: TeamRole
    joined_at: datetime
    name: str | None = None
    email: str | None = None
    evm_wallet_address: str | None = None

    @field_serializer("joined_at")
    @classmethod
    def serialize_datetime(cls, v: datetime) -> str:
        return v.isoformat(timespec="milliseconds")


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
    ] = None
    default_channel: Annotated[
        str | None,
        Field(
            default=None,
            description="Default notification channel (telegram, wechat)",
        ),
    ] = None
    default_channel_chat_id: Annotated[
        str | None,
        Field(
            default=None,
            description="Default push chat ID within the channel",
        ),
    ] = None

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

            try:
                await db.commit()
            except IntegrityError as e:
                # Concurrent request with the same team_id committed first; map
                # to the same validation error so the endpoint returns 400 instead
                # of leaking a 500.
                raise ValueError("Team ID is already taken") from e
            await db.refresh(team_record)
            return Team.model_validate(team_record)


class Team(TeamCreate):
    """Team model with all fields."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        from_attributes=True,
    )

    lead_agent: Annotated[
        dict[str, Any] | None,
        Field(
            default=None,
            exclude=True,
            description="Persisted lead agent config (internal only)",
        ),
    ] = None
    role: Annotated[
        TeamRole | None,
        Field(
            default=None, description="User's role (only set in user-specific queries)"
        ),
    ] = None
    plan: Annotated[
        TeamPlan,
        Field(default=TeamPlan.NONE, description="Pricing plan tier"),
    ] = TeamPlan.NONE

    @field_validator("plan", mode="before")
    @classmethod
    def normalize_plan(cls, v: Any) -> Any:
        """Handle legacy data where str(TeamPlan.X) was stored instead of .value."""
        if isinstance(v, str) and v.startswith("TeamPlan."):
            return v.removeprefix("TeamPlan.").lower()
        return v

    plan_expires_at: Annotated[
        datetime | None,
        Field(default=None, description="When the current plan expires"),
    ] = None
    next_credit_issue_at: Annotated[
        datetime | None,
        Field(default=None, description="Next scheduled monthly credit issue"),
    ] = None
    created_at: Annotated[
        datetime, Field(description="Timestamp when this team was created")
    ]
    updated_at: Annotated[
        datetime, Field(description="Timestamp when this team was last updated")
    ]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def plan_name(self) -> str:
        """Display name derived from the plan's PlanConfig."""
        return PLAN_CONFIGS.get(self.plan, PLAN_CONFIGS[TeamPlan.NONE]).name

    @computed_field  # type: ignore[prop-decorator]
    @property
    def plan_description(self) -> str:
        """Description derived from the plan's PlanConfig."""
        return PLAN_CONFIGS.get(self.plan, PLAN_CONFIGS[TeamPlan.NONE]).description

    @computed_field  # type: ignore[prop-decorator]
    @property
    def plan_seats(self) -> int:
        """Max seats derived from the plan's PlanConfig."""
        return PLAN_CONFIGS.get(self.plan, PLAN_CONFIGS[TeamPlan.NONE]).seats

    @computed_field  # type: ignore[prop-decorator]
    @property
    def plan_month_price_cents(self) -> int:
        """Monthly price in cents derived from the plan's PlanConfig."""
        return PLAN_CONFIGS.get(
            self.plan, PLAN_CONFIGS[TeamPlan.NONE]
        ).month_price_cents

    @computed_field  # type: ignore[prop-decorator]
    @property
    def plan_year_price_cents(self) -> int:
        """Yearly price in cents derived from the plan's PlanConfig."""
        return PLAN_CONFIGS.get(self.plan, PLAN_CONFIGS[TeamPlan.NONE]).year_price_cents

    @field_serializer(
        "created_at", "updated_at", "plan_expires_at", "next_credit_issue_at"
    )
    @classmethod
    def serialize_datetime(cls, v: datetime | None) -> str | None:
        if v is None:
            return None
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
    async def get_lead_agent_config(cls, team_id: str) -> dict[str, Any] | None:
        """Get the persisted lead agent config for a team."""
        async with get_session() as db:
            stmt = select(TeamTable.lead_agent).where(TeamTable.id == team_id)
            return await db.scalar(stmt)

    @classmethod
    async def update_lead_agent_config(
        cls, team_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge updates into the persisted lead agent config atomically.

        Uses PostgreSQL JSONB `||` operator for race-free merge.

        Args:
            team_id: Team ID.
            updates: Fields to merge (name, avatar, personality).

        Returns:
            The updated lead agent config dict.
        """
        from sqlalchemy import cast, func
        from sqlalchemy import update as sa_update

        async with get_session() as db:
            # Atomic JSONB merge: coalesce(lead_agent, '{}') || updates
            merged_expr = func.coalesce(TeamTable.lead_agent, cast({}, JSONB)).concat(
                cast(updates, JSONB)
            )
            await db.execute(
                sa_update(TeamTable)
                .where(TeamTable.id == team_id)
                .values(lead_agent=merged_expr)
            )
            await db.commit()
            # Read back the merged result
            result = await db.scalar(
                select(TeamTable.lead_agent).where(TeamTable.id == team_id)
            )
            return result or {}

    @classmethod
    async def get_by_user(cls, user_id: str) -> list["Team"]:
        """Get all teams a user belongs to, including the user's role."""
        async with get_session() as db:
            stmt = (
                select(TeamTable, TeamMemberTable.role)
                .join(
                    TeamMemberTable,
                    TeamMemberTable.team_id == TeamTable.id,
                )
                .where(TeamMemberTable.user_id == user_id)
                .order_by(TeamTable.name)
            )
            result = await db.execute(stmt)
            teams = []
            for team, role in result:
                t = cls.model_validate(team)
                t.role = role
                teams.append(t)
            return teams


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
