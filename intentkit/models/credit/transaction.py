from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Annotated, Any, ClassVar

from epyxid import XID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    DateTime,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from intentkit.config.base import Base
from intentkit.models.credit.base import CreditType


class TransactionType(str, Enum):
    """Type of credit transaction."""

    PAY = "pay"
    RECEIVE_BASE_LLM = "receive_base_llm"
    RECEIVE_BASE_SKILL = "receive_base_skill"
    RECEIVE_BASE_MEMORY = "receive_base_memory"
    RECEIVE_BASE_VOICE = "receive_base_voice"
    RECEIVE_BASE_KNOWLEDGE = "receive_base_knowledge"
    RECEIVE_FEE_DEV = "receive_fee_dev"
    RECEIVE_FEE_AGENT = "receive_fee_agent"
    RECEIVE_FEE_PLATFORM = "receive_fee_platform"
    RECHARGE = "recharge"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"
    REFILL = "refill"
    WITHDRAW = "withdraw"
    # Sync with RewardType values
    REWARD = "reward"
    EVENT_REWARD = "event_reward"
    RECHARGE_BONUS = "recharge_bonus"


class CreditDebit(str, Enum):
    """Credit or debit transaction."""

    CREDIT = "credit"
    DEBIT = "debit"


class CreditTransactionTable(Base):
    """Credit transactions database table model.

    Records the flow of credits in and out of accounts.
    """

    __tablename__ = "credit_transactions"
    __table_args__ = (
        Index("ix_credit_transactions_account", "account_id"),
        Index("ix_credit_transactions_event_id", "event_id"),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )
    account_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    event_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    tx_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    credit_debit: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    change_amount: Mapped[Decimal] = mapped_column(
        Numeric(22, 4),
        default=0,
        nullable=False,
    )
    free_amount: Mapped[Decimal] = mapped_column(
        Numeric(22, 4),
        default=0,
        nullable=False,
    )
    reward_amount: Mapped[Decimal] = mapped_column(
        Numeric(22, 4),
        default=0,
        nullable=False,
    )
    permanent_amount: Mapped[Decimal] = mapped_column(
        Numeric(22, 4),
        default=0,
        nullable=False,
    )
    credit_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CreditTransaction(BaseModel):
    """Credit transaction model with all fields."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        use_enum_values=True,
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat(timespec="milliseconds")},
    )

    id: Annotated[
        str,
        Field(
            default_factory=lambda: str(XID()),
            description="Unique identifier for the credit transaction",
        ),
    ]
    account_id: Annotated[
        str, Field(description="ID of the account this transaction belongs to")
    ]
    event_id: Annotated[
        str, Field(description="ID of the event that triggered this transaction")
    ]
    tx_type: Annotated[TransactionType, Field(description="Type of the transaction")]
    credit_debit: Annotated[
        CreditDebit, Field(description="Whether this is a credit or debit transaction")
    ]
    change_amount: Annotated[
        Decimal, Field(default=Decimal("0"), description="Amount of credits changed")
    ]
    free_amount: Annotated[
        Decimal,
        Field(default=Decimal("0"), description="Amount of free credits changed"),
    ]
    reward_amount: Annotated[
        Decimal,
        Field(default=Decimal("0"), description="Amount of reward credits changed"),
    ]
    permanent_amount: Annotated[
        Decimal,
        Field(default=Decimal("0"), description="Amount of permanent credits changed"),
    ]

    @field_validator(
        "change_amount", "free_amount", "reward_amount", "permanent_amount"
    )
    @classmethod
    def round_decimal(cls, v: Any) -> Decimal:
        """Round decimal values to 4 decimal places."""
        if isinstance(v, Decimal):
            return v.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        elif isinstance(v, int | float):
            return Decimal(str(v)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        return v

    credit_type: Annotated[CreditType, Field(description="Type of credits involved")]
    created_at: Annotated[
        datetime, Field(description="Timestamp when this transaction was created")
    ]
