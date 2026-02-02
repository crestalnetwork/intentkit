from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal

from epyxid import XID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.db import get_session
from intentkit.models.credit import (
    DEFAULT_PLATFORM_ACCOUNT_REFILL,
    CreditAccount,
    CreditAccountTable,
    CreditDebit,
    CreditEventTable,
    CreditTransactionTable,
    CreditType,
    Direction,
    EventType,
    OwnerType,
    TransactionType,
    UpstreamType,
)

from .base import FOURPLACES

logger = logging.getLogger(__name__)


async def refill_free_credits_for_account(
    session: AsyncSession,
    account: CreditAccount,
):
    """
    Refill free credits for a single account based on its refill_amount and free_quota.

    Args:
        session: Async session to use for database operations
        account: The credit account to refill
    """
    # Skip if refill_amount is zero or free_credits already equals or exceeds free_quota
    if (
        account.refill_amount <= Decimal("0")
        or account.free_credits >= account.free_quota
    ):
        return

    # Calculate the amount to add
    # If adding refill_amount would exceed free_quota, only add what's needed to reach free_quota
    amount_to_add = min(
        account.refill_amount, account.free_quota - account.free_credits
    ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

    if amount_to_add <= Decimal("0"):
        return  # Nothing to add

    # 1. Create credit event record first to get event_id
    event_id = str(XID())

    # 2. Update user account - add free credits
    updated_account = await CreditAccount.income_in_session(
        session=session,
        owner_type=account.owner_type,
        owner_id=account.owner_id,
        amount_details={CreditType.FREE: amount_to_add},
        event_id=event_id,
    )

    # 3. Update platform refill account - deduct credits
    platform_account = await CreditAccount.deduction_in_session(
        session=session,
        owner_type=OwnerType.PLATFORM,
        owner_id=DEFAULT_PLATFORM_ACCOUNT_REFILL,
        credit_type=CreditType.FREE,
        amount=amount_to_add,
        event_id=event_id,
    )

    # 4. Create credit event record
    event = CreditEventTable(
        id=event_id,
        account_id=updated_account.id,
        event_type=EventType.REFILL,
        user_id=account.owner_id,
        upstream_type=UpstreamType.SCHEDULER,
        upstream_tx_id=str(XID()),
        direction=Direction.INCOME,
        credit_type=CreditType.FREE,
        credit_types=[CreditType.FREE],
        total_amount=amount_to_add,
        balance_after=updated_account.credits
        + updated_account.free_credits
        + updated_account.reward_credits,
        base_amount=amount_to_add,
        base_original_amount=amount_to_add,
        base_free_amount=amount_to_add,
        base_reward_amount=Decimal("0"),
        base_permanent_amount=Decimal("0"),
        free_amount=amount_to_add,  # Set free_amount since this is a free credit refill
        reward_amount=Decimal("0"),  # No reward credits involved
        permanent_amount=Decimal("0"),  # No permanent credits involved
        agent_wallet_address=None,  # No agent involved in refill
        note=f"Hourly free credits refill of {amount_to_add}",
    )
    session.add(event)
    await session.flush()

    # 4. Create credit transaction records
    # 4.1 User account transaction (credit)
    user_tx = CreditTransactionTable(
        id=str(XID()),
        account_id=updated_account.id,
        event_id=event_id,
        tx_type=TransactionType.REFILL,
        credit_debit=CreditDebit.CREDIT,
        change_amount=amount_to_add,
        credit_type=CreditType.FREE,
        free_amount=amount_to_add,
        reward_amount=Decimal("0"),
        permanent_amount=Decimal("0"),
    )
    session.add(user_tx)

    # 4.2 Platform refill account transaction (debit)
    platform_tx = CreditTransactionTable(
        id=str(XID()),
        account_id=platform_account.id,
        event_id=event_id,
        tx_type=TransactionType.REFILL,
        credit_debit=CreditDebit.DEBIT,
        change_amount=amount_to_add,
        credit_type=CreditType.FREE,
        free_amount=amount_to_add,
        reward_amount=Decimal("0"),
        permanent_amount=Decimal("0"),
    )
    session.add(platform_tx)

    # Commit changes
    await session.commit()
    logger.info(
        f"Refilled {amount_to_add} free credits for account {account.owner_type} {account.owner_id}"
    )


async def refill_all_free_credits():
    """
    Find all eligible accounts and refill their free credits.
    Eligible accounts are those with refill_amount > 0 and free_credits < free_quota.
    """
    async with get_session() as session:
        # Find all accounts that need refilling
        stmt = select(CreditAccountTable).where(
            CreditAccountTable.refill_amount > 0,
            CreditAccountTable.free_credits < CreditAccountTable.free_quota,
        )
        result = await session.execute(stmt)
        accounts_data = result.scalars().all()

        # Convert to Pydantic models
        accounts = [CreditAccount.model_validate(account) for account in accounts_data]

    # Process each account
    refilled_count = 0
    for account in accounts:
        async with get_session() as session:
            try:
                await refill_free_credits_for_account(session, account)
                refilled_count += 1
            except Exception as e:
                logger.error(f"Error refilling account {account.id}: {str(e)}")
            # Continue with other accounts even if one fails
            continue
    logger.info(f"Refilled {refilled_count} accounts")
