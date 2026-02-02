from __future__ import annotations

import logging
from decimal import Decimal

from epyxid import XID
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.models.credit import (
    DEFAULT_PLATFORM_ACCOUNT_ADJUSTMENT,
    CreditAccount,
    CreditDebit,
    CreditEvent,
    CreditEventTable,
    CreditTransactionTable,
    CreditType,
    Direction,
    EventType,
    OwnerType,
    TransactionType,
    UpstreamType,
)

logger = logging.getLogger(__name__)


async def adjustment(
    session: AsyncSession,
    user_id: str,
    credit_type: CreditType,
    amount: Decimal,
    upstream_tx_id: str,
    note: str,
) -> CreditAccount:
    """
    Adjust a user account's credits (can be positive or negative).

    Args:
        session: Async session to use for database operations
        user_id: ID of the user to adjust
        credit_type: Type of credit to adjust (FREE, REWARD, or PERMANENT)
        amount: Amount to adjust (positive for increase, negative for decrease)
        upstream_tx_id: ID of the upstream transaction
        note: Required explanation for the adjustment

    Returns:
        Updated user credit account
    """
    # Check for idempotency - prevent duplicate transactions
    await CreditEvent.check_upstream_tx_id_exists(
        session, UpstreamType.API, upstream_tx_id
    )

    if amount == Decimal("0"):
        raise ValueError("Adjustment amount cannot be zero")

    if not note:
        raise ValueError("Adjustment requires a note explaining the reason")

    # Determine direction based on amount sign
    is_income = amount > Decimal("0")
    abs_amount = abs(amount)
    direction = Direction.INCOME if is_income else Direction.EXPENSE
    credit_debit_user = CreditDebit.CREDIT if is_income else CreditDebit.DEBIT
    credit_debit_platform = CreditDebit.DEBIT if is_income else CreditDebit.CREDIT

    # 1. Create credit event record first to get event_id
    event_id = str(XID())

    # 2. Update user account
    if is_income:
        user_account = await CreditAccount.income_in_session(
            session=session,
            owner_type=OwnerType.USER,
            owner_id=user_id,
            amount_details={credit_type: abs_amount},
            event_id=event_id,
        )
    else:
        # Deduct the credits using deduction_in_session
        # For adjustment, we don't check if the user has enough credits
        # It can be positive or negative
        user_account = await CreditAccount.deduction_in_session(
            session=session,
            owner_type=OwnerType.USER,
            owner_id=user_id,
            credit_type=credit_type,
            amount=abs_amount,
            event_id=event_id,
        )

    # 3. Update platform adjustment account
    if is_income:
        platform_account = await CreditAccount.deduction_in_session(
            session=session,
            owner_type=OwnerType.PLATFORM,
            owner_id=DEFAULT_PLATFORM_ACCOUNT_ADJUSTMENT,
            credit_type=credit_type,
            amount=abs_amount,
            event_id=event_id,
        )
    else:
        platform_account = await CreditAccount.income_in_session(
            session=session,
            owner_type=OwnerType.PLATFORM,
            owner_id=DEFAULT_PLATFORM_ACCOUNT_ADJUSTMENT,
            amount_details={credit_type: abs_amount},
            event_id=event_id,
        )

    # 4. Create credit event record
    # Set the appropriate credit amount field based on credit type
    free_amount = Decimal("0")
    reward_amount = Decimal("0")
    permanent_amount = Decimal("0")

    if credit_type == CreditType.FREE:
        free_amount = abs_amount
    elif credit_type == CreditType.REWARD:
        reward_amount = abs_amount
    elif credit_type == CreditType.PERMANENT:
        permanent_amount = abs_amount

    event = CreditEventTable(
        id=event_id,
        event_type=EventType.ADJUSTMENT,
        user_id=user_id,
        upstream_type=UpstreamType.API,
        upstream_tx_id=upstream_tx_id,
        direction=direction,
        account_id=user_account.id,
        total_amount=abs_amount,
        credit_type=credit_type,
        credit_types=[credit_type],
        balance_after=user_account.credits
        + user_account.free_credits
        + user_account.reward_credits,
        base_amount=abs_amount,
        base_original_amount=abs_amount,
        base_free_amount=free_amount,
        base_reward_amount=reward_amount,
        base_permanent_amount=permanent_amount,
        free_amount=free_amount,
        reward_amount=reward_amount,
        permanent_amount=permanent_amount,
        agent_wallet_address=None,  # No agent involved in adjustment
        note=note,
    )
    session.add(event)
    await session.flush()

    # 4. Create credit transaction records
    # 4.1 User account transaction
    user_tx = CreditTransactionTable(
        id=str(XID()),
        account_id=user_account.id,
        event_id=event_id,
        tx_type=TransactionType.ADJUSTMENT,
        credit_debit=credit_debit_user,
        change_amount=abs_amount,
        credit_type=credit_type,
        free_amount=free_amount,
        reward_amount=reward_amount,
        permanent_amount=permanent_amount,
    )
    session.add(user_tx)

    # 4.2 Platform adjustment account transaction
    platform_tx = CreditTransactionTable(
        id=str(XID()),
        account_id=platform_account.id,
        event_id=event_id,
        tx_type=TransactionType.ADJUSTMENT,
        credit_debit=credit_debit_platform,
        change_amount=abs_amount,
        credit_type=credit_type,
        free_amount=free_amount,
        reward_amount=reward_amount,
        permanent_amount=permanent_amount,
    )
    session.add(platform_tx)

    # Commit all changes
    await session.commit()

    return user_account
