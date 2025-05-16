import logging
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Annotated, Any, Optional, Tuple

from epyxid import XID
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Numeric,
    String,
    func,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession

from models.base import Base
from models.db import get_session

logger = logging.getLogger(__name__)


class CreditType(str, Enum):
    """Credit type is used in db column names, do not change it."""

    FREE = "free_credits"
    REWARD = "reward_credits"
    PERMANENT = "credits"


class OwnerType(str, Enum):
    """Type of credit account owner."""

    USER = "user"
    AGENT = "agent"
    PLATFORM = "platform"


# Platform virtual account ids/owner ids, they are used for transaction balance tracing
# The owner id and account id are the same
DEFAULT_PLATFORM_ACCOUNT_RECHARGE = "platform_recharge"
DEFAULT_PLATFORM_ACCOUNT_REFILL = "platform_refill"
DEFAULT_PLATFORM_ACCOUNT_ADJUSTMENT = "platform_adjustment"
DEFAULT_PLATFORM_ACCOUNT_REWARD = "platform_reward"
DEFAULT_PLATFORM_ACCOUNT_REFUND = "platform_refund"
DEFAULT_PLATFORM_ACCOUNT_MESSAGE = "platform_message"
DEFAULT_PLATFORM_ACCOUNT_SKILL = "platform_skill"
DEFAULT_PLATFORM_ACCOUNT_FEE = "platform_fee"
DEFAULT_PLATFORM_ACCOUNT_DEV = "platform_dev"


class CreditAccountTable(Base):
    """Credit account database table model."""

    __tablename__ = "credit_accounts"
    __table_args__ = (Index("ix_credit_accounts_owner", "owner_type", "owner_id"),)

    id = Column(
        String,
        primary_key=True,
    )
    owner_type = Column(
        String,
        nullable=False,
    )
    owner_id = Column(
        String,
        nullable=False,
    )
    free_quota = Column(
        Numeric(22, 4),
        default=0,
        nullable=False,
    )
    refill_amount = Column(
        Numeric(22, 4),
        default=0,
        nullable=False,
    )
    free_credits = Column(
        Numeric(22, 4),
        default=0,
        nullable=False,
    )
    reward_credits = Column(
        Numeric(22, 4),
        default=0,
        nullable=False,
    )
    credits = Column(
        Numeric(22, 4),
        default=0,
        nullable=False,
    )
    income_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    expense_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class CreditAccount(BaseModel):
    """Credit account model with all fields."""

    model_config = ConfigDict(
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
            description="Unique identifier for the credit account",
        ),
    ]
    owner_type: Annotated[OwnerType, Field(description="Type of the account owner")]
    owner_id: Annotated[str, Field(description="ID of the account owner")]
    free_quota: Annotated[
        Decimal,
        Field(
            default=Decimal("0"), description="Daily credit quota that resets each day"
        ),
    ]
    refill_amount: Annotated[
        Decimal,
        Field(
            default=Decimal("0"),
            description="Amount to refill hourly, not exceeding free_quota",
        ),
    ]
    free_credits: Annotated[
        Decimal,
        Field(default=Decimal("0"), description="Current available daily credits"),
    ]
    reward_credits: Annotated[
        Decimal,
        Field(
            default=Decimal("0"), description="Reward credits earned through rewards"
        ),
    ]
    credits: Annotated[
        Decimal,
        Field(default=Decimal("0"), description="Credits added through top-ups"),
    ]
    income_at: Annotated[
        Optional[datetime],
        Field(None, description="Timestamp of the last income transaction"),
    ]
    expense_at: Annotated[
        Optional[datetime],
        Field(None, description="Timestamp of the last expense transaction"),
    ]
    created_at: Annotated[
        datetime, Field(description="Timestamp when this account was created")
    ]
    updated_at: Annotated[
        datetime, Field(description="Timestamp when this account was last updated")
    ]

    @field_validator(
        "free_quota", "refill_amount", "free_credits", "reward_credits", "credits"
    )
    @classmethod
    def round_decimal(cls, v: Any) -> Decimal:
        """Round decimal values to 4 decimal places."""
        if isinstance(v, Decimal):
            return v.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        elif isinstance(v, (int, float)):
            return Decimal(str(v)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        return v

    @classmethod
    async def get_in_session(
        cls,
        session: AsyncSession,
        owner_type: OwnerType,
        owner_id: str,
    ) -> "CreditAccount":
        """Get a credit account by owner type and ID.

        Args:
            session: Async session to use for database queries
            owner_type: Type of the owner
            owner_id: ID of the owner

        Returns:
            CreditAccount if found, None otherwise
        """
        stmt = select(CreditAccountTable).where(
            CreditAccountTable.owner_type == owner_type,
            CreditAccountTable.owner_id == owner_id,
        )
        result = await session.scalar(stmt)
        if not result:
            raise HTTPException(status_code=404, detail="Credit account not found")
        return cls.model_validate(result)

    @classmethod
    async def get_or_create_in_session(
        cls,
        session: AsyncSession,
        owner_type: OwnerType,
        owner_id: str,
        for_update: bool = False,
    ) -> "CreditAccount":
        """Get a credit account by owner type and ID.

        Args:
            session: Async session to use for database queries
            owner_type: Type of the owner
            owner_id: ID of the owner

        Returns:
            CreditAccount if found, None otherwise
        """
        stmt = select(CreditAccountTable).where(
            CreditAccountTable.owner_type == owner_type,
            CreditAccountTable.owner_id == owner_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await session.scalar(stmt)
        if not result:
            account = await cls.create_in_session(session, owner_type, owner_id)
        else:
            account = cls.model_validate(result)

        return account

    @classmethod
    async def get_or_create(
        cls, owner_type: OwnerType, owner_id: str
    ) -> "CreditAccount":
        """Get a credit account by owner type and ID.

        Args:
            owner_type: Type of the owner
            owner_id: ID of the owner

        Returns:
            CreditAccount if found, None otherwise
        """
        async with get_session() as session:
            account = await cls.get_or_create_in_session(session, owner_type, owner_id)
            await session.commit()
            return account

    @classmethod
    async def deduction_in_session(
        cls,
        session: AsyncSession,
        owner_type: OwnerType,
        owner_id: str,
        credit_type: CreditType,
        amount: Decimal,
    ) -> "CreditAccount":
        """Deduct credits from an account. Not checking balance"""
        # check first, create if not exists
        await cls.get_or_create_in_session(session, owner_type, owner_id)

        stmt = (
            update(CreditAccountTable)
            .where(
                CreditAccountTable.owner_type == owner_type,
                CreditAccountTable.owner_id == owner_id,
            )
            .values(
                {
                    credit_type.value: getattr(CreditAccountTable, credit_type.value)
                    - amount,
                    "expense_at": datetime.now(timezone.utc),
                }
            )
            .returning(CreditAccountTable)
        )
        res = await session.scalar(stmt)
        if not res:
            raise HTTPException(status_code=500, detail="Failed to expense credits")
        return cls.model_validate(res)

    @classmethod
    async def expense_in_session(
        cls,
        session: AsyncSession,
        owner_type: OwnerType,
        owner_id: str,
        amount: Decimal,
    ) -> Tuple["CreditAccount", CreditType]:
        """Expense credits and return account and credit type.
        We are not checking balance here, since a conversation may have
        multiple expenses, we can't interrupt the conversation.
        """
        # check first
        account = await cls.get_or_create_in_session(session, owner_type, owner_id)

        # expense
        credit_type = CreditType.PERMANENT
        if amount <= account.free_credits:
            credit_type = CreditType.FREE
        elif amount <= account.reward_credits:
            credit_type = CreditType.REWARD

        stmt = (
            update(CreditAccountTable)
            .where(
                CreditAccountTable.owner_type == owner_type,
                CreditAccountTable.owner_id == owner_id,
            )
            .values(
                {
                    credit_type.value: getattr(CreditAccountTable, credit_type.value)
                    - amount,
                    "expense_at": datetime.now(timezone.utc),
                }
            )
            .returning(CreditAccountTable)
        )
        res = await session.scalar(stmt)
        if not res:
            raise HTTPException(status_code=500, detail="Failed to expense credits")
        return cls.model_validate(res), credit_type

    def has_sufficient_credits(self, amount: Decimal) -> bool:
        """Check if the account has enough credits to cover the specified amount.

        Args:
            amount: The amount of credits to check against

        Returns:
            bool: True if there are enough credits, False otherwise
        """
        return amount <= self.free_credits + self.reward_credits + self.credits

    @classmethod
    async def income_in_session(
        cls,
        session: AsyncSession,
        owner_type: OwnerType,
        owner_id: str,
        amount: Decimal,
        credit_type: CreditType,
    ) -> "CreditAccount":
        # check first, create if not exists
        await cls.get_or_create_in_session(session, owner_type, owner_id)
        # income
        stmt = (
            update(CreditAccountTable)
            .where(
                CreditAccountTable.owner_type == owner_type,
                CreditAccountTable.owner_id == owner_id,
            )
            .values(
                {
                    credit_type.value: getattr(CreditAccountTable, credit_type.value)
                    + amount,
                    "income_at": datetime.now(timezone.utc),
                }
            )
            .returning(CreditAccountTable)
        )
        res = await session.scalar(stmt)
        if not res:
            raise HTTPException(status_code=500, detail="Failed to income credits")
        return cls.model_validate(res)

    @classmethod
    async def create_in_session(
        cls,
        session: AsyncSession,
        owner_type: OwnerType,
        owner_id: str,
        free_quota: Decimal = Decimal("480.0"),
        refill_amount: Decimal = Decimal("20.0"),
    ) -> "CreditAccount":
        """Get an existing credit account or create a new one if it doesn't exist.

        This is useful for silent creation of accounts when they're first accessed.

        Args:
            session: Async session to use for database queries
            owner_type: Type of the owner
            owner_id: ID of the owner
            free_quota: Daily quota for a new account if created

        Returns:
            CreditAccount: The existing or newly created credit account
        """
        if owner_type != OwnerType.USER:
            # only users have daily quota
            free_quota = 0.0
            refill_amount = 0.0
        account = CreditAccountTable(
            id=str(XID()),
            owner_type=owner_type,
            owner_id=owner_id,
            free_quota=free_quota,
            refill_amount=refill_amount,
            free_credits=free_quota,
            reward_credits=0.0,
            credits=0.0,
            income_at=datetime.now(timezone.utc),
            expense_at=None,
        )
        # Platform virtual accounts have fixed IDs, same as owner_id
        if owner_type == OwnerType.PLATFORM:
            account.id = owner_id
        session.add(account)
        await session.flush()
        await session.refresh(account)
        # Only user accounts have first refill
        if owner_type == OwnerType.USER:
            # First refill account
            await cls.deduction_in_session(
                session,
                OwnerType.PLATFORM,
                DEFAULT_PLATFORM_ACCOUNT_REFILL,
                CreditType.FREE,
                free_quota,
            )
            # Create refill event record
            event_id = str(XID())
            event = CreditEventTable(
                id=event_id,
                event_type=EventType.REFILL,
                user_id=owner_id,
                upstream_type=UpstreamType.INITIALIZER,
                upstream_tx_id=account.id,
                direction=Direction.INCOME,
                account_id=account.id,
                credit_type=CreditType.FREE,
                total_amount=free_quota,
                balance_after=free_quota,
                base_amount=free_quota,
                base_original_amount=free_quota,
                note="Initial refill",
            )
            session.add(event)
            await session.flush()

            # Create credit transaction records
            # 1. User account transaction (credit)
            user_tx = CreditTransactionTable(
                id=str(XID()),
                account_id=account.id,
                event_id=event_id,
                tx_type=TransactionType.RECHARGE,
                credit_debit=CreditDebit.CREDIT,
                change_amount=free_quota,
                credit_type=CreditType.FREE,
            )
            session.add(user_tx)

            # 2. Platform recharge account transaction (debit)
            platform_tx = CreditTransactionTable(
                id=str(XID()),
                account_id=DEFAULT_PLATFORM_ACCOUNT_REFILL,
                event_id=event_id,
                tx_type=TransactionType.REFILL,
                credit_debit=CreditDebit.DEBIT,
                change_amount=free_quota,
                credit_type=CreditType.FREE,
            )
            session.add(platform_tx)

        return cls.model_validate(account)

    @classmethod
    async def update_daily_quota(
        cls,
        session: AsyncSession,
        user_id: str,
        free_quota: Optional[Decimal] = None,
        refill_amount: Optional[Decimal] = None,
        upstream_tx_id: str = "",
        note: str = "",
    ) -> "CreditAccount":
        """
        Update the daily quota and refill amount of a user's credit account.

        Args:
            session: Async session to use for database operations
            user_id: ID of the user to update
            free_quota: Optional new daily quota value
            refill_amount: Optional amount to refill hourly, not exceeding free_quota
            upstream_tx_id: ID of the upstream transaction (for logging purposes)
            note: Explanation for changing the daily quota

        Returns:
            Updated user credit account
        """
        # Log the upstream_tx_id for record keeping
        logger.info(
            f"Updating quota settings for user {user_id} with upstream_tx_id: {upstream_tx_id}"
        )

        # Check that at least one parameter is provided
        if free_quota is None and refill_amount is None:
            raise ValueError(
                "At least one of free_quota or refill_amount must be provided"
            )

        # Get current account to check existing values and validate
        user_account = await cls.get_or_create_in_session(
            session, OwnerType.USER, user_id, for_update=True
        )

        # Use existing values if not provided
        if free_quota is None:
            free_quota = user_account.free_quota
        elif free_quota <= Decimal("0"):
            raise ValueError("Daily quota must be positive")

        if refill_amount is None:
            refill_amount = user_account.refill_amount
        elif refill_amount < Decimal("0"):
            raise ValueError("Refill amount cannot be negative")

        # Ensure refill_amount doesn't exceed free_quota
        if refill_amount > free_quota:
            raise ValueError("Refill amount cannot exceed daily quota")

        if not note:
            raise ValueError("Quota update requires a note explaining the reason")

        # Update the free_quota field
        stmt = (
            update(CreditAccountTable)
            .where(
                CreditAccountTable.owner_type == OwnerType.USER,
                CreditAccountTable.owner_id == user_id,
            )
            .values(free_quota=free_quota, refill_amount=refill_amount)
            .returning(CreditAccountTable)
        )
        result = await session.scalar(stmt)
        if not result:
            raise ValueError("Failed to update user account")

        user_account = cls.model_validate(result)

        # No credit event needed for updating account settings

        return user_account


class EventType(str, Enum):
    """Type of credit event."""

    MESSAGE = "message"
    SKILL_CALL = "skill_call"
    RECHARGE = "recharge"
    REWARD = "reward"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"
    REFILL = "refill"


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

    id = Column(
        String,
        primary_key=True,
    )
    account_id = Column(
        String,
        nullable=False,
    )
    event_type = Column(
        String,
        nullable=False,
    )
    user_id = Column(
        String,
        nullable=True,
    )
    upstream_type = Column(
        String,
        nullable=False,
    )
    upstream_tx_id = Column(
        String,
        nullable=False,
    )
    agent_id = Column(
        String,
        nullable=True,
    )
    start_message_id = Column(
        String,
        nullable=True,
    )
    message_id = Column(
        String,
        nullable=True,
    )
    skill_call_id = Column(
        String,
        nullable=True,
    )
    direction = Column(
        String,
        nullable=False,
    )
    total_amount = Column(
        Numeric(22, 4),
        default=0,
        nullable=False,
    )
    credit_type = Column(
        String,
        nullable=False,
    )
    balance_after = Column(
        Numeric(22, 4),
        nullable=True,
        default=None,
    )
    base_amount = Column(
        Numeric(22, 4),
        default=0,
        nullable=False,
    )
    base_discount_amount = Column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    base_original_amount = Column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    base_llm_amount = Column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    base_skill_amount = Column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    fee_platform_amount = Column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    fee_dev_account = Column(
        String,
        nullable=True,
    )
    fee_dev_amount = Column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    fee_agent_account = Column(
        String,
        nullable=True,
    )
    fee_agent_amount = Column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    free_amount = Column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    reward_amount = Column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    permanent_amount = Column(
        Numeric(22, 4),
        default=0,
        nullable=True,
    )
    note = Column(
        String,
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CreditEvent(BaseModel):
    """Credit event model with all fields."""

    model_config = ConfigDict(
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
        Optional[str], Field(None, description="ID of the user if applicable")
    ]
    upstream_type: Annotated[
        UpstreamType, Field(description="Type of upstream transaction")
    ]
    upstream_tx_id: Annotated[str, Field(description="Upstream transaction ID if any")]
    agent_id: Annotated[
        Optional[str], Field(None, description="ID of the agent if applicable")
    ]
    start_message_id: Annotated[
        Optional[str],
        Field(None, description="ID of the starting message if applicable"),
    ]
    message_id: Annotated[
        Optional[str], Field(None, description="ID of the message if applicable")
    ]
    skill_call_id: Annotated[
        Optional[str], Field(None, description="ID of the skill call if applicable")
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
    balance_after: Annotated[
        Optional[Decimal],
        Field(None, description="Account total balance after the transaction"),
    ]
    base_amount: Annotated[
        Decimal,
        Field(default=Decimal("0"), description="Base amount of credits involved"),
    ]
    base_discount_amount: Annotated[
        Optional[Decimal],
        Field(default=Decimal("0"), description="Base discount amount"),
    ]
    base_original_amount: Annotated[
        Optional[Decimal],
        Field(default=Decimal("0"), description="Base original amount"),
    ]
    base_llm_amount: Annotated[
        Optional[Decimal],
        Field(default=Decimal("0"), description="Base LLM cost amount"),
    ]
    base_skill_amount: Annotated[
        Optional[Decimal],
        Field(default=Decimal("0"), description="Base skill cost amount"),
    ]
    fee_platform_amount: Annotated[
        Optional[Decimal],
        Field(default=Decimal("0"), description="Platform fee amount"),
    ]
    fee_dev_account: Annotated[
        Optional[str], Field(None, description="Developer account ID receiving fee")
    ]
    fee_dev_amount: Annotated[
        Optional[Decimal],
        Field(default=Decimal("0"), description="Developer fee amount"),
    ]
    fee_agent_account: Annotated[
        Optional[str], Field(None, description="Agent account ID receiving fee")
    ]
    fee_agent_amount: Annotated[
        Optional[Decimal], Field(default=Decimal("0"), description="Agent fee amount")
    ]
    free_amount: Annotated[
        Optional[Decimal],
        Field(default=Decimal("0"), description="Free credit amount involved"),
    ]
    reward_amount: Annotated[
        Optional[Decimal],
        Field(default=Decimal("0"), description="Reward credit amount involved"),
    ]
    permanent_amount: Annotated[
        Optional[Decimal],
        Field(default=Decimal("0"), description="Permanent credit amount involved"),
    ]
    note: Annotated[Optional[str], Field(None, description="Additional notes")]
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
        "fee_platform_amount",
        "fee_dev_amount",
        "fee_agent_amount",
        "free_amount",
        "reward_amount",
        "permanent_amount",
    )
    @classmethod
    def round_decimal(cls, v: Any) -> Optional[Decimal]:
        """Round decimal values to 4 decimal places."""
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        elif isinstance(v, (int, float)):
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


class TransactionType(str, Enum):
    """Type of credit transaction."""

    PAY = "pay"
    RECEIVE_BASE_LLM = "receive_base_llm"
    RECEIVE_BASE_SKILL = "receive_base_skill"
    RECEIVE_FEE_DEV = "receive_fee_dev"
    RECEIVE_FEE_AGENT = "receive_fee_agent"
    RECEIVE_FEE_PLATFORM = "receive_fee_platform"
    RECHARGE = "recharge"
    REWARD = "reward"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"
    REFILL = "refill"


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

    id = Column(
        String,
        primary_key=True,
    )
    account_id = Column(
        String,
        nullable=False,
    )
    event_id = Column(
        String,
        nullable=False,
    )
    tx_type = Column(
        String,
        nullable=False,
    )
    credit_debit = Column(
        String,
        nullable=False,
    )
    change_amount = Column(
        Numeric(22, 4),
        default=0,
        nullable=False,
    )
    credit_type = Column(
        String,
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CreditTransaction(BaseModel):
    """Credit transaction model with all fields."""

    model_config = ConfigDict(
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

    @field_validator("change_amount")
    @classmethod
    def round_decimal(cls, v: Any) -> Decimal:
        """Round decimal values to 4 decimal places."""
        if isinstance(v, Decimal):
            return v.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        elif isinstance(v, (int, float)):
            return Decimal(str(v)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        return v

    credit_type: Annotated[CreditType, Field(description="Type of credits involved")]
    created_at: Annotated[
        datetime, Field(description="Timestamp when this transaction was created")
    ]


class PriceEntity(str, Enum):
    """Type of credit price."""

    SKILL_CALL = "skill_call"


class DiscountType(str, Enum):
    """Type of discount."""

    STANDARD = "standard"
    SELF_KEY = "self_key"


DEFAULT_SKILL_CALL_PRICE = Decimal("10.0000")
DEFAULT_SKILL_CALL_SELF_KEY_PRICE = Decimal("5.0000")


class CreditPriceTable(Base):
    """Credit price database table model.

    Stores price information for different types of services.
    """

    __tablename__ = "credit_prices"

    id = Column(
        String,
        primary_key=True,
    )
    price_entity = Column(
        String,
        nullable=False,
    )
    price_entity_id = Column(
        String,
        nullable=False,
    )
    discount_type = Column(
        String,
        nullable=False,
    )
    price = Column(
        Numeric(22, 4),
        default=0,
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class CreditPrice(BaseModel):
    """Credit price model with all fields."""

    model_config = ConfigDict(
        use_enum_values=True,
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat(timespec="milliseconds")},
    )

    id: Annotated[
        str,
        Field(
            default_factory=lambda: str(XID()),
            description="Unique identifier for the credit price",
        ),
    ]
    price_entity: Annotated[
        PriceEntity, Field(description="Type of the price (agent or skill_call)")
    ]
    price_entity_id: Annotated[
        str, Field(description="ID of the price entity, the skill is the name")
    ]
    discount_type: Annotated[
        DiscountType,
        Field(default=DiscountType.STANDARD, description="Type of discount"),
    ]
    price: Annotated[Decimal, Field(default=Decimal("0"), description="Standard price")]

    @field_validator("price")
    @classmethod
    def round_decimal(cls, v: Any) -> Decimal:
        """Round decimal values to 4 decimal places."""
        if isinstance(v, Decimal):
            return v.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        elif isinstance(v, (int, float)):
            return Decimal(str(v)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        return v

    created_at: Annotated[
        datetime, Field(description="Timestamp when this price was created")
    ]
    updated_at: Annotated[
        datetime, Field(description="Timestamp when this price was last updated")
    ]


class CreditPriceLogTable(Base):
    """Credit price log database table model.

    Records history of price changes.
    """

    __tablename__ = "credit_price_logs"

    id = Column(
        String,
        primary_key=True,
    )
    price_id = Column(
        String,
        nullable=False,
    )
    old_price = Column(
        Numeric(22, 4),
        nullable=False,
    )
    new_price = Column(
        Numeric(22, 4),
        nullable=False,
    )
    note = Column(
        String,
        nullable=True,
    )
    modified_by = Column(
        String,
        nullable=False,
    )
    modified_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CreditPriceLog(BaseModel):
    """Credit price log model with all fields."""

    model_config = ConfigDict(
        use_enum_values=True,
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat(timespec="milliseconds")},
    )

    id: Annotated[
        str,
        Field(
            default_factory=lambda: str(XID()),
            description="Unique identifier for the log entry",
        ),
    ]
    price_id: Annotated[str, Field(description="ID of the price that was modified")]
    old_price: Annotated[Decimal, Field(description="Previous standard price")]
    new_price: Annotated[Decimal, Field(description="New standard price")]

    @field_validator("old_price", "new_price")
    @classmethod
    def round_decimal(cls, v: Any) -> Decimal:
        """Round decimal values to 4 decimal places."""
        if isinstance(v, Decimal):
            return v.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        elif isinstance(v, (int, float)):
            return Decimal(str(v)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        return v

    note: Annotated[
        Optional[str], Field(None, description="Note about the modification")
    ]
    modified_by: Annotated[
        str, Field(description="ID of the user who made the modification")
    ]
    modified_at: Annotated[
        datetime, Field(description="Timestamp when the modification was made")
    ]
