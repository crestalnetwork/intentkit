#!/usr/bin/env python

"""
Data repair script to fix precision issues in credit data.

This script finds all message events in CreditEventTable and checks if the total_amount
is correctly calculated as the sum of base_amount, fee_platform_amount, and fee_agent_amount.
If there's a discrepancy (usually by 0.0001 due to precision issues), it fixes:
1. The total_amount and balance_after in CreditEventTable
2. The change_amount in the corresponding CreditTransactionTable record
3. The user's account balance in CreditAccountTable
"""

import asyncio
import logging
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select

from app.config.config import config
from models.credit import (
    CreditAccountTable,
    CreditEventTable,
    CreditTransactionTable,
    CreditType,
    EventType,
    TransactionType,
)
from models.db import get_session, init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Define the precision for all decimal calculations (4 decimal places)
FOURPLACES = Decimal("0.0001")


async def fix_credit_precision():
    """Fix precision issues in credit data for message events."""
    logger.info("Starting credit precision fix script")

    fixed_count = 0
    async with get_session() as session:
        # Find all message events
        stmt = select(CreditEventTable).where(
            CreditEventTable.event_type == EventType.MESSAGE
        )
        result = await session.execute(stmt)
        events = result.scalars().all()

        logger.info(f"Found {len(events)} message events to check")

        for event in events:
            # Calculate what the total should be
            base_amount = event.base_amount
            fee_platform_amount = event.fee_platform_amount or Decimal("0")
            fee_agent_amount = event.fee_agent_amount or Decimal("0")

            # Calculate the correct total with 4 decimal places
            correct_total = (
                base_amount + fee_platform_amount + fee_agent_amount
            ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

            # Check if there's a discrepancy
            if event.total_amount != correct_total:
                # Calculate the difference
                difference = correct_total - event.total_amount

                logger.info(
                    f"Fixing event {event.id}: Current total={event.total_amount}, "
                    f"Correct total={correct_total}, Difference={difference}"
                )

                # 1. Update the event's total_amount and balance_after
                event.total_amount = correct_total
                if event.balance_after is not None:
                    event.balance_after = (event.balance_after - difference).quantize(
                        FOURPLACES, rounding=ROUND_HALF_UP
                    )

                # 2. Find and update the corresponding transaction
                tx_stmt = select(CreditTransactionTable).where(
                    CreditTransactionTable.event_id == event.id,
                    CreditTransactionTable.tx_type == TransactionType.PAY,
                )
                tx_result = await session.execute(tx_stmt)
                transaction = tx_result.scalar_one_or_none()

                if transaction:
                    transaction.change_amount = correct_total
                    logger.info(
                        f"Updated transaction {transaction.id} change_amount to {correct_total}"
                    )
                else:
                    logger.warning(f"No PAY transaction found for event {event.id}")

                # 3. Update the user's account
                # If the correct total is higher than the original, we need to subtract from the account
                # If the correct total is lower than the original, we need to add to the account
                account_stmt = select(CreditAccountTable).where(
                    CreditAccountTable.id == event.account_id
                )
                account_result = await session.execute(account_stmt)
                account = account_result.scalar_one_or_none()

                if account:
                    # If the event's total increased, the account balance should decrease
                    # If the event's total decreased, the account balance should increase
                    if event.credit_type == CreditType.PERMANENT:
                        account.credits = (account.credits - difference).quantize(
                            FOURPLACES, rounding=ROUND_HALF_UP
                        )
                    elif event.credit_type == CreditType.FREE:
                        account.free_credits = (
                            account.free_credits - difference
                        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)
                    elif event.credit_type == CreditType.REWARD:
                        account.reward_credits = (
                            account.reward_credits - difference
                        ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

                    logger.info(
                        f"Updated account {account.id} balance: "
                        f"credits={account.credits}, "
                        f"free_credits={account.free_credits}, "
                        f"reward_credits={account.reward_credits}"
                    )
                else:
                    logger.warning(f"No account found with ID {event.account_id}")

                fixed_count += 1

        # Commit all changes
        await session.commit()

    logger.info(f"Fixed {fixed_count} events with precision issues")


async def main():
    """Main entry point for the script."""
    # Initialize the database connection
    await init_db(**config.db)

    # Run the fix credit precision function
    await fix_credit_precision()


if __name__ == "__main__":
    asyncio.run(main())
