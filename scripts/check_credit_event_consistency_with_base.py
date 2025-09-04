#!/usr/bin/env python3
"""
Credit Event Consistency Checker with Base Amount Validation

This script checks the consistency of credit event records in the database,
including validation of base amount fields and their relationships.

Base amount validation includes:
1. base_amount = base_free_amount + base_reward_amount + base_permanent_amount
2. base_amount + fee_platform_amount + fee_dev_amount + fee_agent_amount = total_amount
3. Each fee amount should equal the sum of its free/reward/permanent components
4. Base amounts should be consistent with the original credit type breakdown

Usage:
    python scripts/check_credit_event_consistency_with_base.py
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.config import config
from intentkit.models.credit import CreditEventTable
from intentkit.models.db import get_session, init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("credit_event_consistency_check.log"),
    ],
)
logger = logging.getLogger(__name__)

# Constants
BATCH_SIZE = 1000
TOLERANCE = Decimal("0.0001")  # Tolerance for decimal comparison


def to_decimal(value) -> Decimal:
    """Convert value to Decimal, handling None values."""
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


class CreditEventConsistencyChecker:
    """Checker for credit event consistency including base amount validation."""

    def __init__(self):
        self.total_checked = 0
        self.total_inconsistencies = 0
        self.zero_sum_errors = 0
        self.non_zero_sum_errors = 0
        self.base_amount_errors = 0
        self.fee_breakdown_errors = 0
        self.base_fee_total_errors = 0
        self.inconsistent_records: List[Dict] = []

    async def check_all_events(self) -> None:
        """Check all credit events for consistency using cursor-based pagination."""

        async with get_session() as session:
            # Get total count for progress tracking
            total_count = await self._get_total_count(session)
            logger.info(f"Total credit events to check: {total_count:,}")

            last_id = ""
            batch_number = 0

            while True:
                batch_number += 1
                events = await self._get_events_batch(session, last_id, BATCH_SIZE)

                if not events:
                    break

                logger.info(
                    f"Processing batch {batch_number}, starting from ID: {last_id or 'beginning'}, "
                    f"batch size: {len(events)}, progress: {self.total_checked}/{total_count} "
                    f"({self.total_checked / total_count * 100:.1f}%)"
                )

                for event in events:
                    await self._check_event_consistency(event)
                    self.total_checked += 1
                    last_id = event.id

                # Log progress every 10 batches
                if batch_number % 10 == 0:
                    logger.info(
                        f"Progress: {self.total_checked:,}/{total_count:,} events checked "
                        f"({self.total_checked / total_count * 100:.1f}%), "
                        f"found {self.total_inconsistencies} inconsistencies"
                    )

        await self._log_summary()

    async def _get_total_count(self, session: AsyncSession) -> int:
        """Get total count of credit events."""
        stmt = select(func.count(CreditEventTable.id))
        result = await session.scalar(stmt)
        return result or 0

    async def _get_events_batch(
        self, session: AsyncSession, last_id: str, batch_size: int
    ) -> List[CreditEventTable]:
        """Get a batch of credit events using cursor-based pagination."""
        stmt = (
            select(CreditEventTable)
            .where(CreditEventTable.id > last_id)
            .order_by(CreditEventTable.id)
            .limit(batch_size)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def _check_event_consistency(self, event: CreditEventTable) -> None:
        """Check consistency of a single credit event including base amounts."""
        errors = []

        # Convert all amounts to Decimal for consistent calculation
        total_amount = to_decimal(event.total_amount)
        free_amount = to_decimal(event.free_amount)
        reward_amount = to_decimal(event.reward_amount)
        permanent_amount = to_decimal(event.permanent_amount)

        # Base amounts
        base_amount = to_decimal(event.base_amount)
        base_free_amount = to_decimal(event.base_free_amount)
        base_reward_amount = to_decimal(event.base_reward_amount)
        base_permanent_amount = to_decimal(event.base_permanent_amount)

        # Fee amounts
        fee_platform_amount = to_decimal(event.fee_platform_amount)
        fee_dev_amount = to_decimal(event.fee_dev_amount)
        fee_agent_amount = to_decimal(event.fee_agent_amount)

        # Fee breakdown amounts
        fee_platform_free_amount = to_decimal(event.fee_platform_free_amount)
        fee_platform_reward_amount = to_decimal(event.fee_platform_reward_amount)
        fee_platform_permanent_amount = to_decimal(event.fee_platform_permanent_amount)

        fee_dev_free_amount = to_decimal(event.fee_dev_free_amount)
        fee_dev_reward_amount = to_decimal(event.fee_dev_reward_amount)
        fee_dev_permanent_amount = to_decimal(event.fee_dev_permanent_amount)

        fee_agent_free_amount = to_decimal(event.fee_agent_free_amount)
        fee_agent_reward_amount = to_decimal(event.fee_agent_reward_amount)
        fee_agent_permanent_amount = to_decimal(event.fee_agent_permanent_amount)

        # Check 1: Original consistency - total amount vs credit type amounts
        calculated_total = free_amount + reward_amount + permanent_amount
        if abs(total_amount - calculated_total) > TOLERANCE:
            errors.append(
                f"Total amount mismatch: total_amount={total_amount}, "
                f"calculated={calculated_total} (free={free_amount} + reward={reward_amount} + permanent={permanent_amount})"
            )

        # Check 2: Fee amounts consistency
        # Platform fee breakdown
        calculated_platform_fee = (
            fee_platform_free_amount
            + fee_platform_reward_amount
            + fee_platform_permanent_amount
        )
        if abs(fee_platform_amount - calculated_platform_fee) > TOLERANCE:
            errors.append(
                f"Platform fee breakdown mismatch: fee_platform_amount={fee_platform_amount}, "
                f"calculated={calculated_platform_fee} (free={fee_platform_free_amount} + reward={fee_platform_reward_amount} + permanent={fee_platform_permanent_amount})"
            )
            self.fee_breakdown_errors += 1

        # Dev fee breakdown
        calculated_dev_fee = (
            fee_dev_free_amount + fee_dev_reward_amount + fee_dev_permanent_amount
        )
        if abs(fee_dev_amount - calculated_dev_fee) > TOLERANCE:
            errors.append(
                f"Dev fee breakdown mismatch: fee_dev_amount={fee_dev_amount}, "
                f"calculated={calculated_dev_fee} (free={fee_dev_free_amount} + reward={fee_dev_reward_amount} + permanent={fee_dev_permanent_amount})"
            )
            self.fee_breakdown_errors += 1

        # Agent fee breakdown
        calculated_agent_fee = (
            fee_agent_free_amount + fee_agent_reward_amount + fee_agent_permanent_amount
        )
        if abs(fee_agent_amount - calculated_agent_fee) > TOLERANCE:
            errors.append(
                f"Agent fee breakdown mismatch: fee_agent_amount={fee_agent_amount}, "
                f"calculated={calculated_agent_fee} (free={fee_agent_free_amount} + reward={fee_agent_reward_amount} + permanent={fee_agent_permanent_amount})"
            )
            self.fee_breakdown_errors += 1

        # Check 3: Base amount consistency
        calculated_base_amount = (
            base_free_amount + base_reward_amount + base_permanent_amount
        )
        if abs(base_amount - calculated_base_amount) > TOLERANCE:
            errors.append(
                f"Base amount breakdown mismatch: base_amount={base_amount}, "
                f"calculated={calculated_base_amount} (base_free={base_free_amount} + base_reward={base_reward_amount} + base_permanent={base_permanent_amount})"
            )
            self.base_amount_errors += 1

        # Check 4: Base amount + fees = total amount
        calculated_total_from_base_and_fees = (
            base_amount + fee_platform_amount + fee_dev_amount + fee_agent_amount
        )
        if abs(total_amount - calculated_total_from_base_and_fees) > TOLERANCE:
            errors.append(
                f"Base + fees != total: total_amount={total_amount}, "
                f"base_amount + fees={calculated_total_from_base_and_fees} "
                f"(base={base_amount} + platform_fee={fee_platform_amount} + dev_fee={fee_dev_amount} + agent_fee={fee_agent_amount})"
            )
            self.base_fee_total_errors += 1

        # Check 5: Credit type consistency between base amounts and total amounts
        # Base free amount should be consistent with free amount minus fees
        expected_base_free = (
            free_amount
            - fee_platform_free_amount
            - fee_dev_free_amount
            - fee_agent_free_amount
        )
        if abs(base_free_amount - expected_base_free) > TOLERANCE:
            errors.append(
                f"Base free amount inconsistency: base_free_amount={base_free_amount}, "
                f"expected={expected_base_free} (free_amount={free_amount} - platform_fee_free={fee_platform_free_amount} - dev_fee_free={fee_dev_free_amount} - agent_fee_free={fee_agent_free_amount})"
            )

        # Base reward amount should be consistent with reward amount minus fees
        expected_base_reward = (
            reward_amount
            - fee_platform_reward_amount
            - fee_dev_reward_amount
            - fee_agent_reward_amount
        )
        if abs(base_reward_amount - expected_base_reward) > TOLERANCE:
            errors.append(
                f"Base reward amount inconsistency: base_reward_amount={base_reward_amount}, "
                f"expected={expected_base_reward} (reward_amount={reward_amount} - platform_fee_reward={fee_platform_reward_amount} - dev_fee_reward={fee_dev_reward_amount} - agent_fee_reward={fee_agent_reward_amount})"
            )

        # Base permanent amount should be consistent with permanent amount minus fees
        expected_base_permanent = (
            permanent_amount
            - fee_platform_permanent_amount
            - fee_dev_permanent_amount
            - fee_agent_permanent_amount
        )
        if abs(base_permanent_amount - expected_base_permanent) > TOLERANCE:
            errors.append(
                f"Base permanent amount inconsistency: base_permanent_amount={base_permanent_amount}, "
                f"expected={expected_base_permanent} (permanent_amount={permanent_amount} - platform_fee_permanent={fee_platform_permanent_amount} - dev_fee_permanent={fee_dev_permanent_amount} - agent_fee_permanent={fee_agent_permanent_amount})"
            )

        if errors:
            self.total_inconsistencies += 1

            # Categorize error type
            if total_amount == Decimal("0"):
                self.zero_sum_errors += 1
                error_type = "ZERO_SUM_ERROR"
            else:
                self.non_zero_sum_errors += 1
                error_type = "NON_ZERO_SUM_ERROR"

            inconsistent_record = {
                "id": event.id,
                "event_type": event.event_type,
                "user_id": event.user_id,
                "agent_id": event.agent_id,
                "total_amount": str(total_amount),
                "error_type": error_type,
                "errors": errors,
                "created_at": event.created_at.isoformat()
                if event.created_at
                else None,
            }
            self.inconsistent_records.append(inconsistent_record)

            # Log first few errors for immediate visibility
            if self.total_inconsistencies <= 10:
                logger.warning(
                    f"Inconsistency found in event {event.id} ({error_type}): {'; '.join(errors)}"
                )

    async def _log_summary(self) -> None:
        """Log summary of the consistency check."""
        logger.info("\n" + "=" * 80)
        logger.info("CREDIT EVENT CONSISTENCY CHECK SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total events checked: {self.total_checked:,}")
        logger.info(f"Total inconsistencies found: {self.total_inconsistencies:,}")
        logger.info(f"  - Zero-sum errors: {self.zero_sum_errors:,}")
        logger.info(f"  - Non-zero-sum errors: {self.non_zero_sum_errors:,}")
        logger.info(f"  - Base amount errors: {self.base_amount_errors:,}")
        logger.info(f"  - Fee breakdown errors: {self.fee_breakdown_errors:,}")
        logger.info(f"  - Base+fees!=total errors: {self.base_fee_total_errors:,}")

        if self.total_inconsistencies > 0:
            consistency_rate = (
                (self.total_checked - self.total_inconsistencies)
                / self.total_checked
                * 100
            )
            logger.info(f"Consistency rate: {consistency_rate:.2f}%")

            # Log some example inconsistencies
            logger.info("\nExample inconsistencies:")
            for i, record in enumerate(self.inconsistent_records[:5]):
                logger.info(
                    f"  {i + 1}. Event {record['id']} ({record['error_type']}):"
                )
                for error in record["errors"][:2]:  # Show first 2 errors per record
                    logger.info(f"     - {error}")
                if len(record["errors"]) > 2:
                    logger.info(f"     ... and {len(record['errors']) - 2} more errors")
        else:
            logger.info("✅ All credit events are consistent!")

        logger.info("=" * 80)


async def main():
    """Main function to run the consistency check."""
    logger.info("Starting CreditEvent consistency check with base amount validation...")

    # Initialize database connection
    await init_db(**config.db)

    checker = CreditEventConsistencyChecker()
    await checker.check_all_events()


if __name__ == "__main__":
    asyncio.run(main())
