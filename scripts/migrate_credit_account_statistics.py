#!/usr/bin/env python3
"""
Migration script to populate new statistics fields in credit_accounts table.

This script calculates and populates the following fields based on transaction history:
- total_income, total_free_income, total_reward_income, total_permanent_income
- total_expense, total_free_expense, total_reward_expense, total_permanent_expense

The script locks three tables (credit_accounts, credit_transactions, credit_events)
for each record to prevent interference from running programs.
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.models.db import get_session

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def create_backup_table(session: AsyncSession) -> None:
    """Create a backup of the credit_accounts table before migration."""
    backup_table_name = "credit_accounts_backup_statistics_migration"

    # Check if backup table already exists
    check_query = text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :table_name)"
    )
    exists = await session.scalar(check_query, {"table_name": backup_table_name})

    if exists:
        logger.info(
            f"Backup table {backup_table_name} already exists, skipping creation"
        )
        return

    # Create backup table
    backup_query = text(
        f"CREATE TABLE {backup_table_name} AS SELECT * FROM credit_accounts"
    )
    await session.execute(backup_query)
    await session.commit()
    logger.info(f"Created backup table: {backup_table_name}")


async def calculate_statistics_from_transactions(
    session: AsyncSession, account_id: str
) -> Dict[str, Decimal]:
    """Calculate statistics for a specific account from transaction history.

    Args:
        session: Database session with proper locks
        account_id: ID of the credit account

    Returns:
        Dictionary with calculated statistics
    """
    # Lock tables to prevent concurrent modifications
    await session.execute(text("LOCK TABLE credit_accounts IN EXCLUSIVE MODE"))
    await session.execute(text("LOCK TABLE credit_transactions IN SHARE MODE"))
    await session.execute(text("LOCK TABLE credit_events IN SHARE MODE"))

    # Query to calculate statistics from transactions
    query = text("""
        SELECT 
            -- Income calculations (credit_debit = 'credit')
            COALESCE(SUM(CASE WHEN credit_debit = 'credit' THEN change_amount ELSE 0 END), 0) as total_income,
            COALESCE(SUM(CASE WHEN credit_debit = 'credit' THEN free_amount ELSE 0 END), 0) as total_free_income,
            COALESCE(SUM(CASE WHEN credit_debit = 'credit' THEN reward_amount ELSE 0 END), 0) as total_reward_income,
            COALESCE(SUM(CASE WHEN credit_debit = 'credit' THEN permanent_amount ELSE 0 END), 0) as total_permanent_income,
            -- Expense calculations (credit_debit = 'debit')
            COALESCE(SUM(CASE WHEN credit_debit = 'debit' THEN change_amount ELSE 0 END), 0) as total_expense,
            COALESCE(SUM(CASE WHEN credit_debit = 'debit' THEN free_amount ELSE 0 END), 0) as total_free_expense,
            COALESCE(SUM(CASE WHEN credit_debit = 'debit' THEN reward_amount ELSE 0 END), 0) as total_reward_expense,
            COALESCE(SUM(CASE WHEN credit_debit = 'debit' THEN permanent_amount ELSE 0 END), 0) as total_permanent_expense
        FROM credit_transactions 
        WHERE account_id = :account_id
    """)

    result = await session.execute(query, {"account_id": account_id})
    row = result.fetchone()

    if not row:
        # No transactions found, return zero values
        return {
            "total_income": Decimal("0"),
            "total_free_income": Decimal("0"),
            "total_reward_income": Decimal("0"),
            "total_permanent_income": Decimal("0"),
            "total_expense": Decimal("0"),
            "total_free_expense": Decimal("0"),
            "total_reward_expense": Decimal("0"),
            "total_permanent_expense": Decimal("0"),
        }

    return {
        "total_income": Decimal(str(row.total_income)),
        "total_free_income": Decimal(str(row.total_free_income)),
        "total_reward_income": Decimal(str(row.total_reward_income)),
        "total_permanent_income": Decimal(str(row.total_permanent_income)),
        "total_expense": Decimal(str(row.total_expense)),
        "total_free_expense": Decimal(str(row.total_free_expense)),
        "total_reward_expense": Decimal(str(row.total_reward_expense)),
        "total_permanent_expense": Decimal(str(row.total_permanent_expense)),
    }


async def update_account_statistics(
    session: AsyncSession, account_id: str, statistics: Dict[str, Decimal]
) -> bool:
    """Update account statistics in the database.

    Args:
        session: Database session with proper locks
        account_id: ID of the credit account
        statistics: Dictionary with calculated statistics

    Returns:
        True if update was successful, False otherwise
    """
    try:
        update_query = text("""
            UPDATE credit_accounts 
            SET 
                total_income = :total_income,
                total_free_income = :total_free_income,
                total_reward_income = :total_reward_income,
                total_permanent_income = :total_permanent_income,
                total_expense = :total_expense,
                total_free_expense = :total_free_expense,
                total_reward_expense = :total_reward_expense,
                total_permanent_expense = :total_permanent_expense,
                updated_at = NOW()
            WHERE id = :account_id
        """)

        result = await session.execute(
            update_query, {"account_id": account_id, **statistics}
        )

        if result.rowcount == 0:
            logger.error(f"No account found with ID: {account_id}")
            return False

        logger.info(f"Updated statistics for account {account_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to update account {account_id}: {e}")
        return False


async def process_single_account(account_id: str) -> bool:
    """Process a single account with proper transaction management.

    Args:
        account_id: ID of the credit account to process

    Returns:
        True if processing was successful, False otherwise
    """
    async with get_session() as session:
        try:
            # Calculate statistics from transactions (with table locks)
            statistics = await calculate_statistics_from_transactions(
                session, account_id
            )

            # Update account with calculated statistics
            success = await update_account_statistics(session, account_id, statistics)

            if success:
                await session.commit()
                logger.info(f"Successfully processed account {account_id}")
                return True
            else:
                await session.rollback()
                logger.error(f"Failed to process account {account_id}")
                return False

        except Exception as e:
            await session.rollback()
            logger.error(f"Error processing account {account_id}: {e}")
            return False


async def get_all_account_ids() -> List[str]:
    """Get all credit account IDs from the database.

    Returns:
        List of account IDs
    """
    async with get_session() as session:
        query = text("SELECT id FROM credit_accounts ORDER BY created_at")
        result = await session.execute(query)
        return [row.id for row in result.fetchall()]


async def main():
    """Main migration function."""
    logger.info("Starting credit account statistics migration")

    try:
        # Create backup table
        async with get_session() as session:
            await create_backup_table(session)

        # Get all account IDs
        account_ids = await get_all_account_ids()
        logger.info(f"Found {len(account_ids)} accounts to process")

        if not account_ids:
            logger.info("No accounts found, migration complete")
            return

        # Process each account
        success_count = 0
        failure_count = 0

        for i, account_id in enumerate(account_ids, 1):
            logger.info(f"Processing account {i}/{len(account_ids)}: {account_id}")

            success = await process_single_account(account_id)
            if success:
                success_count += 1
            else:
                failure_count += 1

            # Log progress every 100 accounts
            if i % 100 == 0:
                logger.info(f"Progress: {i}/{len(account_ids)} accounts processed")

        logger.info(
            f"Migration complete: {success_count} successful, {failure_count} failed"
        )

        if failure_count > 0:
            logger.warning("Some accounts failed to migrate. Check logs for details.")

    except Exception as e:
        logger.error(f"Migration failed with error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
