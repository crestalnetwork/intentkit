from __future__ import annotations

import logging
from decimal import Decimal

from epyxid import XID
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.models.credit import (
    DEFAULT_PLATFORM_ACCOUNT_RECHARGE,
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
from intentkit.utils.alert import send_alert

logger = logging.getLogger(__name__)


async def recharge(
    session: AsyncSession,
    user_id: str,
    amount: Decimal,
    upstream_tx_id: str,
    note: str | None = None,
) -> CreditAccount:
    """
    Recharge credits to a user account.

    Args:
        session: Async session to use for database operations
        user_id: ID of the user to recharge
        amount: Amount of credits to recharge
        upstream_tx_id: ID of the upstream transaction
        note: Optional note for the transaction

    Returns:
        Updated user credit account
    """
    # Check for idempotency - prevent duplicate transactions
    await CreditEvent.check_upstream_tx_id_exists(
        session, UpstreamType.API, upstream_tx_id
    )

    if amount <= Decimal("0"):
        raise ValueError("Recharge amount must be positive")

    # 1. Create credit event record first to get event_id
    event_id = str(XID())

    # 2. Update user account - add credits
    user_account = await CreditAccount.income_in_session(
        session=session,
        owner_type=OwnerType.USER,
        owner_id=user_id,
        amount_details={
            CreditType.PERMANENT: amount
        },  # Recharge adds to permanent credits
        event_id=event_id,
    )

    # 3. Update platform recharge account - deduct credits
    platform_account = await CreditAccount.deduction_in_session(
        session=session,
        owner_type=OwnerType.PLATFORM,
        owner_id=DEFAULT_PLATFORM_ACCOUNT_RECHARGE,
        credit_type=CreditType.PERMANENT,
        amount=amount,
        event_id=event_id,
    )

    # 4. Create credit event record
    event = CreditEventTable(
        id=event_id,
        event_type=EventType.RECHARGE,
        user_id=user_id,
        upstream_type=UpstreamType.API,
        upstream_tx_id=upstream_tx_id,
        direction=Direction.INCOME,
        account_id=user_account.id,
        total_amount=amount,
        credit_type=CreditType.PERMANENT,
        credit_types=[CreditType.PERMANENT],
        balance_after=user_account.credits
        + user_account.free_credits
        + user_account.reward_credits,
        base_amount=amount,
        base_original_amount=amount,
        base_free_amount=Decimal("0"),  # No free credits involved in base amount
        base_reward_amount=Decimal("0"),  # No reward credits involved in base amount
        base_permanent_amount=amount,  # All base amount is permanent for recharge
        permanent_amount=amount,  # Set permanent_amount since this is a permanent credit
        free_amount=Decimal("0"),  # No free credits involved
        reward_amount=Decimal("0"),  # No reward credits involved
        agent_wallet_address=None,  # No agent involved in recharge
        note=note,
    )
    session.add(event)
    await session.flush()

    # 4. Create credit transaction records
    # 4.1 User account transaction (credit)
    user_tx = CreditTransactionTable(
        id=str(XID()),
        account_id=user_account.id,
        event_id=event_id,
        tx_type=TransactionType.RECHARGE,
        credit_debit=CreditDebit.CREDIT,
        change_amount=amount,
        credit_type=CreditType.PERMANENT,
        free_amount=Decimal("0"),
        reward_amount=Decimal("0"),
        permanent_amount=amount,
    )
    session.add(user_tx)

    # 4.2 Platform recharge account transaction (debit)
    platform_tx = CreditTransactionTable(
        id=str(XID()),
        account_id=platform_account.id,
        event_id=event_id,
        tx_type=TransactionType.RECHARGE,
        credit_debit=CreditDebit.DEBIT,
        change_amount=amount,
        credit_type=CreditType.PERMANENT,
        free_amount=Decimal("0"),
        reward_amount=Decimal("0"),
        permanent_amount=amount,
    )
    session.add(platform_tx)

    # Commit all changes
    await session.commit()

    # Send notification for recharge
    try:
        send_alert(
            f"💰 **Credit Recharge**\n"
            f"• User ID: `{user_id}`\n"
            f"• Amount: `{amount}` credits\n"
            f"• Transaction ID: `{upstream_tx_id}`\n"
            f"• New Balance: `{user_account.credits + user_account.free_credits + user_account.reward_credits}` credits\n"
            f"• Note: {note or 'N/A'}"
        )
    except Exception as e:
        logger.error(f"Failed to send notification for recharge: {str(e)}")

    return user_account
