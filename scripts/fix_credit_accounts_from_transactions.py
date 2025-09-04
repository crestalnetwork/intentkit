#!/usr/bin/env python3
"""
Credit Account Migration Script

This script migrates credit data in the CreditAccountTable by recalculating
free_credits, reward_credits, and credits from transaction history.
"""

import argparse
import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.config import config
from intentkit.models.db import get_session, init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def create_backup_table(session: AsyncSession) -> str:
    """Create a backup of the credit_accounts table.

    Returns:
        The name of the backup table
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_table_name = f"credit_accounts_backup_{timestamp}"

    # Create backup table with same structure and data
    backup_sql = f"""
    CREATE TABLE {backup_table_name} AS 
    SELECT * FROM credit_accounts;
    """

    await session.execute(text(backup_sql))
    await session.commit()

    logger.info(f"Created backup table: {backup_table_name}")
    return backup_table_name


async def calculate_credits_from_transactions(
    session: AsyncSession, account_id: str
) -> Tuple[Decimal, Decimal, Decimal]:
    """Calculate the three types of credits from transactions for an account.

    Args:
        session: Database session
        account_id: Account ID to calculate for

    Returns:
        Tuple of (free_credits, reward_credits, credits) calculated from transactions
    """
    # Lock both tables to prevent interference
    await session.execute(text("LOCK TABLE credit_accounts IN EXCLUSIVE MODE"))
    await session.execute(text("LOCK TABLE credit_transactions IN SHARE MODE"))

    # Calculate credits from transactions using SQL
    # Note: permanent_amount corresponds to credits field
    # CREDIT transactions add to balance, DEBIT transactions subtract
    calc_sql = text("""
    SELECT 
        COALESCE(SUM(
            CASE WHEN credit_debit = 'credit' THEN free_amount 
                 WHEN credit_debit = 'debit' THEN -free_amount 
                 ELSE 0 END
        ), 0) as calculated_free_credits,
        COALESCE(SUM(
            CASE WHEN credit_debit = 'credit' THEN reward_amount 
                 WHEN credit_debit = 'debit' THEN -reward_amount 
                 ELSE 0 END
        ), 0) as calculated_reward_credits,
        COALESCE(SUM(
            CASE WHEN credit_debit = 'credit' THEN permanent_amount 
                 WHEN credit_debit = 'debit' THEN -permanent_amount 
                 ELSE 0 END
        ), 0) as calculated_credits
    FROM credit_transactions 
    WHERE account_id = :account_id
    """)

    result = await session.execute(calc_sql, {"account_id": account_id})
    row = result.fetchone()

    if row is None:
        return Decimal("0"), Decimal("0"), Decimal("0")

    return (
        Decimal(str(row.calculated_free_credits)),
        Decimal(str(row.calculated_reward_credits)),
        Decimal(str(row.calculated_credits)),
    )


async def get_current_account_credits(
    session: AsyncSession, account_id: str
) -> Tuple[Decimal, Decimal, Decimal]:
    """Get current credit values from account table.

    Args:
        session: Database session
        account_id: Account ID

    Returns:
        Tuple of (free_credits, reward_credits, credits) from account table
    """
    query = text("""
    SELECT free_credits, reward_credits, credits 
    FROM credit_accounts 
    WHERE id = :account_id
    """)

    result = await session.execute(query, {"account_id": account_id})
    row = result.fetchone()

    if row is None:
        raise ValueError(f"Account {account_id} not found")

    return (
        Decimal(str(row.free_credits)),
        Decimal(str(row.reward_credits)),
        Decimal(str(row.credits)),
    )


async def update_account_credits(
    session: AsyncSession,
    account_id: str,
    free_credits: Decimal,
    reward_credits: Decimal,
    credits: Decimal,
) -> None:
    """Update account with new credit values.

    Args:
        session: Database session
        account_id: Account ID to update
        free_credits: New free credits value
        reward_credits: New reward credits value
        credits: New credits value
    """
    update_sql = text("""
    UPDATE credit_accounts 
    SET free_credits = :free_credits,
        reward_credits = :reward_credits,
        credits = :credits,
        updated_at = NOW()
    WHERE id = :account_id
    """)

    await session.execute(
        update_sql,
        {
            "account_id": account_id,
            "free_credits": free_credits,
            "reward_credits": reward_credits,
            "credits": credits,
        },
    )


async def process_single_account(
    account_id: str, dry_run: bool = False
) -> tuple[bool, bool]:
    """Process a single account in its own session.

    Args:
        account_id: Account ID to process
        dry_run: If True, only check for changes without updating

    Returns:
        Tuple of (success, changed) where:
        - success: True if successful, False if there was a mismatch
        - changed: True if values were different and needed updating, False if no change
    """
    async with get_session() as session:
        try:
            # Get current values
            (
                current_free,
                current_reward,
                current_permanent,
            ) = await get_current_account_credits(session, account_id)
            current_total = current_free + current_reward + current_permanent

            # Calculate from transactions
            (
                calc_free,
                calc_reward,
                calc_permanent,
            ) = await calculate_credits_from_transactions(session, account_id)
            calc_total = calc_free + calc_reward + calc_permanent

            logger.info(
                f"Account {account_id}: Current=({current_free}, {current_reward}, {current_permanent}) "
                f"Total={current_total}, Calculated=({calc_free}, {calc_reward}, {calc_permanent}) "
                f"Total={calc_total}"
            )

            # Check if totals match
            if abs(current_total - calc_total) > Decimal("0.0001"):
                logger.error(
                    f"MISMATCH for account {account_id}! "
                    f"Current total: {current_total}, Calculated total: {calc_total}, "
                    f"Difference: {current_total - calc_total}"
                )
                logger.error(
                    f"Current: free={current_free}, reward={current_reward}, credits={current_permanent}"
                )
                logger.error(
                    f"Calculated: free={calc_free}, reward={calc_reward}, credits={calc_permanent}"
                )
                return False, False

            # Check if values have changed
            values_changed = (
                current_free != calc_free
                or current_reward != calc_reward
                or current_permanent != calc_permanent
            )

            # Update account with calculated values if not dry run and values changed
            if not dry_run and values_changed:
                await update_account_credits(
                    session, account_id, calc_free, calc_reward, calc_permanent
                )
                await session.commit()
                logger.info(f"Successfully updated account {account_id}")
            elif values_changed:
                logger.info(f"Account {account_id} would be updated (dry run mode)")
            else:
                logger.debug(f"Account {account_id} values are already correct")

            return True, values_changed

        except Exception as e:
            logger.error(f"Error processing account {account_id}: {e}")
            await session.rollback()
            raise


async def get_all_account_ids(session: AsyncSession) -> list[str]:
    """Get all account IDs from the database.

    Args:
        session: Database session

    Returns:
        List of account IDs
    """
    query = text("SELECT id FROM credit_accounts ORDER BY id")
    result = await session.execute(query)
    return [row.id for row in result.fetchall()]


async def main(dry_run: bool = False) -> None:
    """
    Main migration function.

    Args:
        dry_run: If True, only check for mismatches without updating
    """
    await init_db(**config.db)

    async with get_session() as session:
        # Create backup table
        if not dry_run:
            backup_table = await create_backup_table(session)
            logger.info(f"Backup created: {backup_table}")

        # Get all account IDs
        account_ids = await get_all_account_ids(session)
        logger.info(f"Found {len(account_ids)} accounts to process")

    # Process each account in its own session
    success_count = 0
    mismatch_count = 0
    unchanged_count = 0
    updated_count = 0

    for i, account_id in enumerate(account_ids, 1):
        logger.info(f"Processing account {i}/{len(account_ids)}: {account_id}")

        try:
            success, changed = await process_single_account(account_id, dry_run)
            if success:
                success_count += 1
                if changed:
                    updated_count += 1
                else:
                    unchanged_count += 1
            else:
                mismatch_count += 1
                if not dry_run:
                    logger.error(
                        "Stopping migration due to mismatch. Please investigate."
                    )
                    break
        except Exception as e:
            logger.error(f"Failed to process account {account_id}: {e}")
            mismatch_count += 1
            if not dry_run:
                logger.error("Stopping migration due to error. Please investigate.")
                break

    logger.info(
        f"Migration {'check' if dry_run else 'process'} completed. "
        f"Total processed: {success_count}, Unchanged: {unchanged_count}, "
        f"Updated: {updated_count}, Mismatches/Errors: {mismatch_count}"
    )

    if mismatch_count > 0:
        logger.error(
            f"Found {mismatch_count} accounts with mismatches or errors. "
            "Please investigate before proceeding."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fix credit account balances from transactions"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only check for mismatches without making changes",
    )

    args = parser.parse_args()

    asyncio.run(main(dry_run=args.dry_run))
