#!/usr/bin/env python

"""
Script to identify records in CreditTransactionTable where
free_amount + reward_amount + permanent_amount != change_amount.

This script helps identify inconsistent data that needs to be migrated.
"""

import asyncio
import logging
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import text

from intentkit.config.config import config
from intentkit.models.db import get_session, init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Define the precision for all decimal calculations (4 decimal places)
FOURPLACES = Decimal("0.0001")


def to_decimal(value) -> Decimal:
    """Convert value to Decimal with proper precision."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value.quantize(FOURPLACES, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(FOURPLACES, rounding=ROUND_HALF_UP)


async def check_transaction_consistency():
    """Check consistency of credit transaction amounts using SQL aggregation."""
    async with get_session() as session:
        # SQL query to count consistent and inconsistent records
        consistency_query = """
        SELECT 
            COUNT(*) as total_count,
            SUM(CASE 
                WHEN ROUND(COALESCE(free_amount, 0) + COALESCE(reward_amount, 0) + COALESCE(permanent_amount, 0), 4) = ROUND(COALESCE(change_amount, 0), 4) 
                THEN 1 
                ELSE 0 
            END) as consistent_count,
            SUM(CASE 
                WHEN ROUND(COALESCE(free_amount, 0) + COALESCE(reward_amount, 0) + COALESCE(permanent_amount, 0), 4) != ROUND(COALESCE(change_amount, 0), 4) 
                THEN 1 
                ELSE 0 
            END) as inconsistent_count
        FROM credit_transactions
        """

        result = await session.execute(text(consistency_query))
        row = result.fetchone()

        total_count = row.total_count
        consistent_count = row.consistent_count
        inconsistent_count = row.inconsistent_count

        logger.info(
            f"Checking {total_count} credit transaction records using SQL aggregation..."
        )

        # Calculate inconsistency rate
        inconsistency_rate = (
            (inconsistent_count / total_count * 100) if total_count > 0 else 0
        )

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("CONSISTENCY CHECK SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total records checked: {total_count}")
        logger.info(f"Inconsistent records found: {inconsistent_count}")
        logger.info(f"Consistent records: {consistent_count}")
        logger.info(f"Inconsistency rate: {inconsistency_rate:.2f}%")

        if inconsistent_count > 0:
            logger.warning(
                f"Found {inconsistent_count} records where "
                f"free_amount + reward_amount + permanent_amount != change_amount"
            )
            logger.info("These records need to be migrated using the migration script.")
        else:
            logger.info("✅ All records are consistent!")

        return inconsistent_count


async def check_missing_event_ids():
    """Check for transactions without event_id."""
    async with get_session() as session:
        # SQL query to count transactions without event_id
        missing_event_id_query = """
        SELECT COUNT(*) as missing_count
        FROM credit_transactions
        WHERE event_id IS NULL OR event_id = ''
        """

        result = await session.execute(text(missing_event_id_query))
        missing_count = result.scalar()

        logger.info("\n" + "=" * 60)
        logger.info("MISSING EVENT ID CHECK")
        logger.info("=" * 60)

        if missing_count > 0:
            logger.warning(f"Found {missing_count} transactions without event_id")

            # Get some examples of transactions without event_id
            sample_query = """
            SELECT id, account_id, tx_type, credit_type, change_amount, created_at
            FROM credit_transactions
            WHERE event_id IS NULL OR event_id = ''
            ORDER BY created_at DESC
            LIMIT 5
            """

            sample_result = await session.execute(text(sample_query))
            samples = sample_result.fetchall()

            logger.warning("Sample transactions without event_id:")
            for sample in samples:
                logger.warning(
                    f"  ID: {sample.id}, Account: {sample.account_id}, "
                    f"Type: {sample.tx_type}, Amount: {sample.change_amount}, "
                    f"Created: {sample.created_at}"
                )
        else:
            logger.info("✅ All transactions have event_id!")

        return missing_count


async def main():
    """Main function to run the consistency check."""
    try:
        await init_db(**config.db)

        # Run both checks
        inconsistent_count = await check_transaction_consistency()
        missing_event_id_count = await check_missing_event_ids()

        # Final summary
        logger.info("\n" + "=" * 60)
        logger.info("FINAL SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Inconsistent amount records: {inconsistent_count}")
        logger.info(f"Missing event_id records: {missing_event_id_count}")

        if inconsistent_count > 0 or missing_event_id_count > 0:
            logger.info("\nNext steps:")
            if inconsistent_count > 0:
                logger.info("1. Run the migration script to fix inconsistent records")
            if missing_event_id_count > 0:
                logger.info("2. Investigate transactions without event_id")
            logger.info("3. Re-run this check script to verify fixes")

        return inconsistent_count
    except Exception as e:
        logger.error(f"Error during consistency check: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
