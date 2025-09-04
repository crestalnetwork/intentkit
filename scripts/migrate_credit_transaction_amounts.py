#!/usr/bin/env python3
"""
Migrate credit transaction amounts based on TransactionType.

This script updates the three new fields (free_amount, reward_amount, permanent_amount)
in CreditTransactionTable based on the transaction type and corresponding fields
from CreditEventTable.
"""

import argparse
import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.config import config
from intentkit.models.db import get_session, init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def count_inconsistent_transactions(session: AsyncSession) -> int:
    """
    Count transactions where free_amount + reward_amount + permanent_amount != change_amount.
    """
    query = text("""
        SELECT COUNT(*) as count
        FROM credit_transactions ct
        JOIN credit_events ce ON ct.event_id = ce.id
        WHERE ROUND(COALESCE(ct.free_amount, 0) + COALESCE(ct.reward_amount, 0) + COALESCE(ct.permanent_amount, 0), 4) 
              != ROUND(COALESCE(ct.change_amount, 0), 4)
    """)
    result = await session.execute(query)
    return result.scalar()


async def migrate_transaction_amounts(
    session: AsyncSession, dry_run: bool = True
) -> None:
    """
    Migrate transaction amounts based on TransactionType.
    """
    # Count records to migrate
    total_records = await count_inconsistent_transactions(session)
    logger.info(f"Found {total_records} transactions to migrate")

    if total_records == 0:
        logger.info("No records to migrate")
        return

    if dry_run:
        logger.info("DRY RUN MODE - No actual changes will be made")
        # Preview first 10 records that would be updated
        preview_query = text("""
            SELECT 
                ct.id,
                ct.tx_type,
                ct.change_amount,
                ct.free_amount as current_free,
                ct.reward_amount as current_reward,
                ct.permanent_amount as current_permanent,
                CASE 
                    WHEN ct.tx_type IN ('pay', 'recharge', 'refund', 'adjustment', 'refill', 'reward', 'event_reward', 'recharge_bonus') THEN
                        COALESCE(ce.free_amount, 0)
                    WHEN ct.tx_type IN ('receive_base_llm', 'receive_base_skill', 'receive_base_memory', 'receive_base_voice', 'receive_base_knowledge') THEN
                        COALESCE(ce.base_free_amount, 0)
                    WHEN ct.tx_type = 'receive_fee_dev' THEN
                        COALESCE(ce.fee_dev_free_amount, 0)
                    WHEN ct.tx_type = 'receive_fee_agent' THEN
                        COALESCE(ce.fee_agent_free_amount, 0)
                    WHEN ct.tx_type = 'receive_fee_platform' THEN
                        COALESCE(ce.fee_platform_free_amount, 0)
                    ELSE 0
                END as new_free,
                CASE 
                    WHEN ct.tx_type IN ('pay', 'recharge', 'refund', 'adjustment', 'refill', 'reward', 'event_reward', 'recharge_bonus') THEN
                        COALESCE(ce.reward_amount, 0)
                    WHEN ct.tx_type IN ('receive_base_llm', 'receive_base_skill', 'receive_base_memory', 'receive_base_voice', 'receive_base_knowledge') THEN
                        COALESCE(ce.base_reward_amount, 0)
                    WHEN ct.tx_type = 'receive_fee_dev' THEN
                        COALESCE(ce.fee_dev_reward_amount, 0)
                    WHEN ct.tx_type = 'receive_fee_agent' THEN
                        COALESCE(ce.fee_agent_reward_amount, 0)
                    WHEN ct.tx_type = 'receive_fee_platform' THEN
                        COALESCE(ce.fee_platform_reward_amount, 0)
                    ELSE 0
                END as new_reward,
                CASE 
                    WHEN ct.tx_type IN ('pay', 'recharge', 'refund', 'adjustment', 'refill', 'reward', 'event_reward', 'recharge_bonus') THEN
                        COALESCE(ce.permanent_amount, 0)
                    WHEN ct.tx_type IN ('receive_base_llm', 'receive_base_skill', 'receive_base_memory', 'receive_base_voice', 'receive_base_knowledge') THEN
                        COALESCE(ce.base_permanent_amount, 0)
                    WHEN ct.tx_type = 'receive_fee_dev' THEN
                        COALESCE(ce.fee_dev_permanent_amount, 0)
                    WHEN ct.tx_type = 'receive_fee_agent' THEN
                        COALESCE(ce.fee_agent_permanent_amount, 0)
                    WHEN ct.tx_type = 'receive_fee_platform' THEN
                        COALESCE(ce.fee_platform_permanent_amount, 0)
                    ELSE 0
                END as new_permanent
            FROM credit_transactions ct
            JOIN credit_events ce ON ct.event_id = ce.id
            WHERE ROUND(COALESCE(ct.free_amount, 0) + COALESCE(ct.reward_amount, 0) + COALESCE(ct.permanent_amount, 0), 4) 
                  != ROUND(COALESCE(ct.change_amount, 0), 4)
            LIMIT 10
        """)
        result = await session.execute(preview_query)
        records = result.fetchall()

        logger.info("Preview of records to be updated:")
        for record in records:
            logger.info(
                f"ID: {record.id}, Type: {record.tx_type}, Change: {record.change_amount}, "
                f"Free: {record.current_free} -> {record.new_free}, "
                f"Reward: {record.current_reward} -> {record.new_reward}, "
                f"Permanent: {record.current_permanent} -> {record.new_permanent}"
            )

        logger.info(
            f"Total {total_records} records would be updated. Use --execute to perform actual migration."
        )
        return

    # Perform actual migration with multiple UPDATE statements for different transaction types
    logger.info("Starting actual migration...")

    # Group 1: PAY, RECHARGE, REFUND, ADJUSTMENT, REFILL, REWARD, EVENT_REWARD, RECHARGE_BONUS
    # These map to event's free_amount, reward_amount, permanent_amount
    update_query_group1 = text("""
        UPDATE credit_transactions 
        SET 
            free_amount = COALESCE(ce.free_amount, 0),
            reward_amount = COALESCE(ce.reward_amount, 0),
            permanent_amount = COALESCE(ce.permanent_amount, 0)
        FROM credit_events ce
        WHERE credit_transactions.event_id = ce.id
        AND credit_transactions.tx_type IN ('pay', 'recharge', 'refund', 'adjustment', 'refill', 'reward', 'event_reward', 'recharge_bonus')
        AND ROUND(COALESCE(credit_transactions.free_amount, 0) + COALESCE(credit_transactions.reward_amount, 0) + COALESCE(credit_transactions.permanent_amount, 0), 4) 
            != ROUND(COALESCE(credit_transactions.change_amount, 0), 4)
    """)

    # Group 2: RECEIVE_BASE_* types
    # These map to event's base_free_amount, base_reward_amount, base_permanent_amount
    update_query_group2 = text("""
        UPDATE credit_transactions 
        SET 
            free_amount = COALESCE(ce.base_free_amount, 0),
            reward_amount = COALESCE(ce.base_reward_amount, 0),
            permanent_amount = COALESCE(ce.base_permanent_amount, 0)
        FROM credit_events ce
        WHERE credit_transactions.event_id = ce.id
        AND credit_transactions.tx_type IN ('receive_base_llm', 'receive_base_skill', 'receive_base_memory', 'receive_base_voice', 'receive_base_knowledge')
        AND ROUND(COALESCE(credit_transactions.free_amount, 0) + COALESCE(credit_transactions.reward_amount, 0) + COALESCE(credit_transactions.permanent_amount, 0), 4) 
            != ROUND(COALESCE(credit_transactions.change_amount, 0), 4)
    """)

    # Group 3: RECEIVE_FEE_DEV
    # Maps to event's fee_dev_free_amount, fee_dev_reward_amount, fee_dev_permanent_amount
    update_query_group3 = text("""
        UPDATE credit_transactions 
        SET 
            free_amount = COALESCE(ce.fee_dev_free_amount, 0),
            reward_amount = COALESCE(ce.fee_dev_reward_amount, 0),
            permanent_amount = COALESCE(ce.fee_dev_permanent_amount, 0)
        FROM credit_events ce
        WHERE credit_transactions.event_id = ce.id
        AND credit_transactions.tx_type = 'receive_fee_dev'
        AND ROUND(COALESCE(credit_transactions.free_amount, 0) + COALESCE(credit_transactions.reward_amount, 0) + COALESCE(credit_transactions.permanent_amount, 0), 4) 
            != ROUND(COALESCE(credit_transactions.change_amount, 0), 4)
    """)

    # Group 4: RECEIVE_FEE_AGENT
    # Maps to event's fee_agent_free_amount, fee_agent_reward_amount, fee_agent_permanent_amount
    update_query_group4 = text("""
        UPDATE credit_transactions 
        SET 
            free_amount = COALESCE(ce.fee_agent_free_amount, 0),
            reward_amount = COALESCE(ce.fee_agent_reward_amount, 0),
            permanent_amount = COALESCE(ce.fee_agent_permanent_amount, 0)
        FROM credit_events ce
        WHERE credit_transactions.event_id = ce.id
        AND credit_transactions.tx_type = 'receive_fee_agent'
        AND ROUND(COALESCE(credit_transactions.free_amount, 0) + COALESCE(credit_transactions.reward_amount, 0) + COALESCE(credit_transactions.permanent_amount, 0), 4) 
            != ROUND(COALESCE(credit_transactions.change_amount, 0), 4)
    """)

    # Group 5: RECEIVE_FEE_PLATFORM
    # Maps to event's fee_platform_free_amount, fee_platform_reward_amount, fee_platform_permanent_amount
    update_query_group5 = text("""
        UPDATE credit_transactions 
        SET 
            free_amount = COALESCE(ce.fee_platform_free_amount, 0),
            reward_amount = COALESCE(ce.fee_platform_reward_amount, 0),
            permanent_amount = COALESCE(ce.fee_platform_permanent_amount, 0)
        FROM credit_events ce
        WHERE credit_transactions.event_id = ce.id
        AND credit_transactions.tx_type = 'receive_fee_platform'
        AND ROUND(COALESCE(credit_transactions.free_amount, 0) + COALESCE(credit_transactions.reward_amount, 0) + COALESCE(credit_transactions.permanent_amount, 0), 4) 
            != ROUND(COALESCE(credit_transactions.change_amount, 0), 4)
    """)

    # Execute all update queries
    queries = [
        ("Group 1 (pay, recharge, etc.)", update_query_group1),
        ("Group 2 (receive_base_*)", update_query_group2),
        ("Group 3 (receive_fee_dev)", update_query_group3),
        ("Group 4 (receive_fee_agent)", update_query_group4),
        ("Group 5 (receive_fee_platform)", update_query_group5),
    ]

    total_updated = 0
    for group_name, query in queries:
        result = await session.execute(query)
        updated_count = result.rowcount
        logger.info(f"{group_name}: Updated {updated_count} records")
        total_updated += updated_count

    await session.commit()
    logger.info(
        f"Migration completed successfully. Total updated: {total_updated} records"
    )


async def verify_migration(session: AsyncSession) -> None:
    """
    Verify the migration by checking for remaining inconsistencies.
    """
    inconsistent_count = await count_inconsistent_transactions(session)

    if inconsistent_count == 0:
        logger.info("✅ Migration verification passed: All records are now consistent")
    else:
        logger.warning(
            f"⚠️  Migration verification found {inconsistent_count} records still inconsistent"
        )
        logger.warning(
            "This may indicate data integrity issues that require manual review"
        )


async def main() -> None:
    """
    Main function to run the migration.
    """
    parser = argparse.ArgumentParser(
        description="Migrate credit transaction amounts based on TransactionType"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the migration (default is dry-run mode)",
    )
    args = parser.parse_args()

    # Initialize database connection
    await init_db(**config.db)

    async with get_session() as session:
        try:
            await migrate_transaction_amounts(session, dry_run=not args.execute)
            if args.execute:
                await verify_migration(session)
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())
