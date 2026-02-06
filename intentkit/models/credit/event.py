from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Annotated, Any, ClassVar

from epyxid import XID
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    ARRAY,
    JSON,
    DateTime,
    Index,
    Numeric,
    String,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.config.base import Base
from intentkit.models.credit.base import CreditType


class RewardType(str, Enum):
    """Reward type enumeration for reward-specific events."""

    REWARD = "reward"
    EVENT_REWARD = "event_reward"
    RECHARGE_BONUS = "recharge_bonus"


class EventType(str, Enum):
    """Type of credit event."""

    MEMORY = "memory"
    MESSAGE = "message"
    SKILL_CALL = "skill_call"
    VOICE = "voice"
    KNOWLEDGE_BASE = "knowledge_base"
    RECHARGE = "recharge"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"
    REFILL = "refill"
    WITHDRAW = "withdraw"
    # Sync with RewardType values
    REWARD = "reward"
    EVENT_REWARD = "event_reward"
    RECHARGE_BONUS = "recharge_bonus"

    @classmethod
    def get_reward_types(cls):
        """Get all reward-related event types"""
        return [cls.REWARD, cls.EVENT_REWARD, cls.RECHARGE_BONUS]


class UpstreamType(str, Enum):
    """Type of upstream transaction."""

    API = "api"
    SCHEDULER = "scheduler"
    EXECUTOR = "executor"
    INITIALIZER = "initializer"


class Direction(str, Enum):
    """Direction of credit flow."""

    INCOME = "income"
    EXPENSE = "expense"


class CreditEventTable(Base):
    """Credit events database table model.

    Records business events for user, like message processing, skill calls, etc.
    """

    __tablename__ = "credit_events"
    __table_args__ = (
        Index(
            "ix_credit_events_upstream", "upstream_type", "upstream_tx_id", unique=True
        ),
        Index("ix_credit_events_account_id", "account_id"),
        Index("ix_credit_events_user_id", "user_id"),
        Index("ix_credit_events_agent_id", "agent_id"),
        Index("ix_credit_events_fee_dev", "fee_dev_account"),
        Index("ix_credit_events_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )
    account_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    user_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    team_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    upstream_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    upstream_tx_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    agent_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    agent_wallet_address: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    start_message_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    message_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    model: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    skill_call_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    skill_name: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    direction: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(22, 4),
        default=0,
        nullable=False,
    )
    credit_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    credit_types: Mapped[list[str] | None] = mapped_column(
        JSON().with_variant(ARRAY(String), "postgresql"),
        nullable=True,
    )
    balance_after: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        nullable=True,
        default=None,
    )
    base_amount: Mapped[Decimal] = mapped_column(
        Numeric(22, 4),
        default=0,
        nullable=False,
    )
    base_discount_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    base_original_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    base_llm_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    base_skill_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    base_free_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    base_reward_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    base_permanent_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    fee_platform_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    fee_platform_free_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        nullable=True,
    )
    fee_platform_reward_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        nullable=True,
    )
    fee_platform_permanent_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        nullable=True,
    )
    fee_dev_account: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    fee_dev_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    fee_dev_free_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        nullable=True,
    )
    fee_dev_reward_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        nullable=True,
    )
    fee_dev_permanent_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        nullable=True,
    )
    fee_agent_account: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    fee_agent_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    fee_agent_free_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        nullable=True,
    )
    fee_agent_reward_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        nullable=True,
    )
    fee_agent_permanent_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        nullable=True,
    )
    free_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    reward_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    permanent_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    note: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CreditEvent(BaseModel):
    """Credit event model with all fields."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        use_enum_values=True,
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat(timespec="milliseconds"),
        },
    )

    id: Annotated[
        str,
        Field(
            default_factory=lambda: str(XID()),
            description="Unique identifier for the credit event",
        ),
    ]
    account_id: Annotated[
        str, Field(None, description="Account ID from which credits flow")
    ]
    event_type: Annotated[EventType, Field(description="Type of the event")]
    user_id: Annotated[
        str | None, Field(None, description="ID of the user if applicable")
    ]
    team_id: Annotated[
        str | None, Field(None, description="ID of the team if applicable")
    ]
    upstream_type: Annotated[
        UpstreamType, Field(description="Type of upstream transaction")
    ]
    upstream_tx_id: Annotated[str, Field(description="Upstream transaction ID if any")]
    agent_id: Annotated[
        str | None, Field(None, description="ID of the agent if applicable")
    ]
    agent_wallet_address: Annotated[
        str | None,
        Field(None, description="Wallet address of the agent if applicable"),
    ]
    start_message_id: Annotated[
        str | None,
        Field(None, description="ID of the starting message if applicable"),
    ]
    message_id: Annotated[
        str | None, Field(None, description="ID of the message if applicable")
    ]
    model: Annotated[
        str | None, Field(None, description="LLM model used if applicable")
    ]
    skill_call_id: Annotated[
        str | None, Field(None, description="ID of the skill call if applicable")
    ]
    skill_name: Annotated[
        str | None, Field(None, description="Name of the skill if applicable")
    ]
    direction: Annotated[Direction, Field(description="Direction of the credit flow")]
    total_amount: Annotated[
        Decimal,
        Field(
            default=Decimal("0"),
            description="Total amount (after discount) of credits involved",
        ),
    ]
    credit_type: Annotated[CreditType, Field(description="Type of credits involved")]
    credit_types: Annotated[
        list[CreditType] | None,
        Field(default=None, description="Array of credit types involved"),
    ]
    balance_after: Annotated[
        Decimal | None,
        Field(None, description="Account total balance after the transaction"),
    ]
    base_amount: Annotated[
        Decimal,
        Field(default=Decimal("0"), description="Base amount of credits involved"),
    ]
    base_discount_amount: Annotated[
        Decimal | None,
        Field(default=Decimal("0"), description="Base discount amount"),
    ]
    base_original_amount: Annotated[
        Decimal | None,
        Field(default=Decimal("0"), description="Base original amount"),
    ]
    base_llm_amount: Annotated[
        Decimal | None,
        Field(default=Decimal("0"), description="Base LLM cost amount"),
    ]
    base_skill_amount: Annotated[
        Decimal | None,
        Field(default=Decimal("0"), description="Base skill cost amount"),
    ]
    base_free_amount: Annotated[
        Decimal | None,
        Field(default=Decimal("0"), description="Base free credit amount"),
    ]
    base_reward_amount: Annotated[
        Decimal | None,
        Field(default=Decimal("0"), description="Base reward credit amount"),
    ]
    base_permanent_amount: Annotated[
        Decimal | None,
        Field(default=Decimal("0"), description="Base permanent credit amount"),
    ]
    fee_platform_amount: Annotated[
        Decimal | None,
        Field(default=Decimal("0"), description="Platform fee amount"),
    ]
    fee_platform_free_amount: Annotated[
        Decimal | None,
        Field(
            default=Decimal("0"), description="Platform fee amount from free credits"
        ),
    ]
    fee_platform_reward_amount: Annotated[
        Decimal | None,
        Field(
            default=Decimal("0"), description="Platform fee amount from reward credits"
        ),
    ]
    fee_platform_permanent_amount: Annotated[
        Decimal | None,
        Field(
            default=Decimal("0"),
            description="Platform fee amount from permanent credits",
        ),
    ]
    fee_dev_account: Annotated[
        str | None, Field(None, description="Developer account ID receiving fee")
    ]
    fee_dev_amount: Annotated[
        Decimal | None,
        Field(default=Decimal("0"), description="Developer fee amount"),
    ]
    fee_dev_free_amount: Annotated[
        Decimal | None,
        Field(
            default=Decimal("0"), description="Developer fee amount from free credits"
        ),
    ]
    fee_dev_reward_amount: Annotated[
        Decimal | None,
        Field(
            default=Decimal("0"), description="Developer fee amount from reward credits"
        ),
    ]
    fee_dev_permanent_amount: Annotated[
        Decimal | None,
        Field(
            default=Decimal("0"),
            description="Developer fee amount from permanent credits",
        ),
    ]
    fee_agent_account: Annotated[
        str | None, Field(None, description="Agent account ID receiving fee")
    ]
    fee_agent_amount: Annotated[
        Decimal | None, Field(default=Decimal("0"), description="Agent fee amount")
    ]
    fee_agent_free_amount: Annotated[
        Decimal | None,
        Field(default=Decimal("0"), description="Agent fee amount from free credits"),
    ]
    fee_agent_reward_amount: Annotated[
        Decimal | None,
        Field(default=Decimal("0"), description="Agent fee amount from reward credits"),
    ]
    fee_agent_permanent_amount: Annotated[
        Decimal | None,
        Field(
            default=Decimal("0"), description="Agent fee amount from permanent credits"
        ),
    ]
    free_amount: Annotated[
        Decimal | None,
        Field(default=Decimal("0"), description="Free credit amount involved"),
    ]
    reward_amount: Annotated[
        Decimal | None,
        Field(default=Decimal("0"), description="Reward credit amount involved"),
    ]
    permanent_amount: Annotated[
        Decimal | None,
        Field(default=Decimal("0"), description="Permanent credit amount involved"),
    ]
    note: Annotated[str | None, Field(None, description="Additional notes")]
    created_at: Annotated[
        datetime, Field(description="Timestamp when this event was created")
    ]

    @field_validator(
        "total_amount",
        "balance_after",
        "base_amount",
        "base_discount_amount",
        "base_original_amount",
        "base_llm_amount",
        "base_skill_amount",
        "base_free_amount",
        "base_reward_amount",
        "base_permanent_amount",
        "fee_platform_amount",
        "fee_platform_free_amount",
        "fee_platform_reward_amount",
        "fee_platform_permanent_amount",
        "fee_dev_amount",
        "fee_dev_free_amount",
        "fee_dev_reward_amount",
        "fee_dev_permanent_amount",
        "fee_agent_amount",
        "fee_agent_free_amount",
        "fee_agent_reward_amount",
        "fee_agent_permanent_amount",
        "free_amount",
        "reward_amount",
        "permanent_amount",
    )
    @classmethod
    def round_decimal(cls, v: Any) -> Decimal | None:
        """Round decimal values to 4 decimal places."""
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        elif isinstance(v, int | float):
            return Decimal(str(v)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        return v

    @classmethod
    async def check_upstream_tx_id_exists(
        cls, session: AsyncSession, upstream_type: UpstreamType, upstream_tx_id: str
    ) -> None:
        """
        Check if an event with the given upstream_type and upstream_tx_id already exists.
        Raises HTTP 400 error if it exists to prevent duplicate transactions.

        Args:
            session: Database session
            upstream_type: Type of the upstream transaction
            upstream_tx_id: ID of the upstream transaction

        Raises:
            HTTPException: If a transaction with the same upstream_tx_id already exists
        """
        stmt = select(CreditEventTable).where(
            CreditEventTable.upstream_type == upstream_type,
            CreditEventTable.upstream_tx_id == upstream_tx_id,
        )
        result = await session.scalar(stmt)
        if result:
            raise HTTPException(
                status_code=400,
                detail=f"Transaction with upstream_tx_id '{upstream_tx_id}' already exists. Do not resubmit.",
            )
