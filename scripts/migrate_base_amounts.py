#!/usr/bin/env python3
"""
Migration script to populate base_free_amount, base_reward_amount, and base_permanent_amount
for existing credit events where these fields are all zero.

This script uses the same algorithm as the expense_skill function to calculate the base amounts
by subtracting platform, agent, and dev fees from the respective credit type amounts.
"""

import asyncio
import logging
from decimal import ROUND_HALF_UP, Decimal
from typing import List

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.config import config
from intentkit.core.credit import FOURPLACES
from intentkit.models.credit import CreditEventTable
from intentkit.models.db import get_session, init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def calculate_base_amounts(
    event: CreditEventTable,
) -> tuple[Decimal, Decimal, Decimal]:
    """
    Calculate base amounts using the same algorithm as expense_skill function.

    Args:
        event: CreditEventTable instance

    Returns:
        Tuple of (base_free_amount, base_reward_amount, base_permanent_amount)
    """
    # Get the credit type amounts
    free_amount = event.free_amount or Decimal("0")
    reward_amount = event.reward_amount or Decimal("0")
    permanent_amount = event.permanent_amount or Decimal("0")

    # Get fee amounts by credit type
    fee_platform_free_amount = event.fee_platform_free_amount or Decimal("0")
    fee_platform_reward_amount = event.fee_platform_reward_amount or Decimal("0")
    fee_platform_permanent_amount = event.fee_platform_permanent_amount or Decimal("0")

    fee_agent_free_amount = event.fee_agent_free_amount or Decimal("0")
    fee_agent_reward_amount = event.fee_agent_reward_amount or Decimal("0")
    fee_agent_permanent_amount = event.fee_agent_permanent_amount or Decimal("0")

    fee_dev_free_amount = event.fee_dev_free_amount or Decimal("0")
    fee_dev_reward_amount = event.fee_dev_reward_amount or Decimal("0")
    fee_dev_permanent_amount = event.fee_dev_permanent_amount or Decimal("0")

    # Calculate base amounts by subtracting all fees from respective credit type amounts
    base_free_amount = (
        free_amount
        - fee_platform_free_amount
        - fee_agent_free_amount
        - fee_dev_free_amount
    ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

    base_reward_amount = (
        reward_amount
        - fee_platform_reward_amount
        - fee_agent_reward_amount
        - fee_dev_reward_amount
    ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

    base_permanent_amount = (
        permanent_amount
        - fee_platform_permanent_amount
        - fee_agent_permanent_amount
        - fee_dev_permanent_amount
    ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

    return base_free_amount, base_reward_amount, base_permanent_amount


async def get_events_to_migrate(
    session: AsyncSession, last_id: str, batch_size: int = 1000
) -> List[CreditEventTable]:
    """
    Get credit events that need migration using cursor-based pagination.

    Args:
        session: Database session
        last_id: Last processed record ID for cursor-based pagination
        batch_size: Number of records to process in each batch

    Returns:
        List of CreditEventTable instances that need migration
    """
    stmt = (
        select(CreditEventTable)
        .where(
            and_(
                CreditEventTable.base_free_amount == Decimal("0"),
                CreditEventTable.base_reward_amount == Decimal("0"),
                CreditEventTable.base_permanent_amount == Decimal("0"),
                CreditEventTable.id > last_id if last_id else True,
            )
        )
        .order_by(CreditEventTable.id)
        .limit(batch_size)
    )

    result = await session.execute(stmt)
    return result.scalars().all()


async def migrate_batch(session: AsyncSession, events: List[CreditEventTable]) -> int:
    """
    Migrate a batch of credit events using bulk updates for better performance.

    Args:
        session: Database session
        events: List of events to migrate

    Returns:
        Number of events successfully migrated
    """
    updates = []
    failed_count = 0

    # Prepare updates for all events
    for event in events:
        try:
            # Calculate the correct base amounts
            (
                base_free_amount,
                base_reward_amount,
                base_permanent_amount,
            ) = calculate_base_amounts(event)

            # Prepare update data
            updates.append(
                {
                    "id": event.id,
                    "base_free_amount": base_free_amount,
                    "base_reward_amount": base_reward_amount,
                    "base_permanent_amount": base_permanent_amount,
                }
            )

        except Exception as e:
            logger.error(f"Error calculating base amounts for event {event.id}: {e}")
            failed_count += 1
            continue

    # Apply bulk updates
    successful_count = 0
    if updates:
        try:
            # Use bulk update for better performance
            for update_data in updates:
                event_id = update_data.pop("id")
                stmt = (
                    update(CreditEventTable)
                    .where(CreditEventTable.id == event_id)
                    .values(**update_data)
                )
                await session.execute(stmt)

            await session.commit()
            successful_count = len(updates)
            logger.info(f"Successfully migrated {successful_count} events")

        except Exception as e:
            logger.error(f"Error committing batch updates: {e}")
            await session.rollback()
            return 0

    if failed_count > 0:
        logger.warning(f"Failed to process {failed_count} events in this batch")

    return successful_count


async def get_total_count(session: AsyncSession) -> int:
    """
    Get total count of events that need migration.

    Args:
        session: Database session

    Returns:
        Total count of events to migrate
    """
    from sqlalchemy import func

    stmt = select(func.count(CreditEventTable.id)).where(
        and_(
            CreditEventTable.base_free_amount == Decimal("0"),
            CreditEventTable.base_reward_amount == Decimal("0"),
            CreditEventTable.base_permanent_amount == Decimal("0"),
        )
    )

    result = await session.execute(stmt)
    return result.scalar() or 0


async def main():
    """
    Main migration function using cursor-based pagination.
    """
    logger.info("Starting base amounts migration...")

    # Initialize database connection
    await init_db(**config.db)

    async with get_session() as session:
        # Get total count first
        total_count = await get_total_count(session)
        logger.info(f"Found {total_count} events to migrate")

        if total_count == 0:
            logger.info("No events need migration. Exiting.")
            return

        # Process in batches using cursor-based pagination
        batch_size = 1000
        total_migrated = 0
        last_id = ""
        batch_number = 1

        while True:
            # Get next batch using cursor-based pagination
            events = await get_events_to_migrate(session, last_id, batch_size)

            if not events:
                logger.info("No more events to migrate")
                break

            logger.info(
                f"Processing batch {batch_number} of {len(events)} events, starting from ID {events[0].id}..."
            )

            # Update cursor to the last processed record's ID
            last_id = events[-1].id

            # Migrate the batch
            migrated_count = await migrate_batch(session, events)
            total_migrated += migrated_count

            logger.info(
                f"Progress: {total_migrated}/{total_count} events migrated ({(total_migrated / total_count) * 100:.1f}%)"
            )

            # If we migrated fewer events than the batch size, log warning
            if migrated_count < len(events):
                logger.warning(
                    f"Some events in batch failed to migrate: {migrated_count}/{len(events)} successful"
                )

            batch_number += 1

            # Small delay to avoid overwhelming the database
            await asyncio.sleep(0.1)

    logger.info(f"Migration completed. Total events migrated: {total_migrated}")


if __name__ == "__main__":
    asyncio.run(main())
