#!/usr/bin/env python3
"""
Credit Event Consistency Checker

This script checks the consistency of credit amounts in CreditEvent records.
It verifies that the sum of free/reward/permanent amounts equals the total amounts
for platform fees, dev fees, agent fees, and total amounts.
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.config import config
from intentkit.models.credit import CreditEventTable
from intentkit.models.db import get_session, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CreditEventConsistencyChecker:
    """Checker for credit event consistency."""

    def __init__(self):
        self.total_records = 0
        self.consistent_records = 0
        self.inconsistent_records = 0
        self.zero_sum_inconsistent_count = (
            0  # Cases where detail sum is 0 but total is not 0
        )
        self.zero_sum_inconsistent_details: List[
            Dict
        ] = []  # Cases where detail sum is 0 but total is not 0
        self.non_zero_sum_inconsistent_details: List[
            Dict
        ] = []  # Unexpected errors where details are non-zero but still unequal

    def check_record_consistency(
        self, record: CreditEventTable
    ) -> Tuple[bool, List[str], bool]:
        """Check if a single record is consistent.

        Returns:
            Tuple of (is_consistent, list_of_errors, is_zero_sum_error)
        """
        errors = []

        # Helper function to safely convert to Decimal
        def to_decimal(value) -> Decimal:
            if value is None:
                return Decimal("0")
            return Decimal(str(value))

        # Check platform fee consistency
        platform_free = to_decimal(record.fee_platform_free_amount)
        platform_reward = to_decimal(record.fee_platform_reward_amount)
        platform_permanent = to_decimal(record.fee_platform_permanent_amount)
        platform_total = to_decimal(record.fee_platform_amount)

        platform_sum = platform_free + platform_reward + platform_permanent
        if platform_sum != platform_total:
            errors.append(
                f"Platform fee mismatch: {platform_free} + {platform_reward} + {platform_permanent} = {platform_sum} != {platform_total}"
            )

        # Check dev fee consistency
        dev_free = to_decimal(record.fee_dev_free_amount)
        dev_reward = to_decimal(record.fee_dev_reward_amount)
        dev_permanent = to_decimal(record.fee_dev_permanent_amount)
        dev_total = to_decimal(record.fee_dev_amount)

        dev_sum = dev_free + dev_reward + dev_permanent
        if dev_sum != dev_total:
            errors.append(
                f"Dev fee mismatch: {dev_free} + {dev_reward} + {dev_permanent} = {dev_sum} != {dev_total}"
            )

        # Check agent fee consistency
        agent_free = to_decimal(record.fee_agent_free_amount)
        agent_reward = to_decimal(record.fee_agent_reward_amount)
        agent_permanent = to_decimal(record.fee_agent_permanent_amount)
        agent_total = to_decimal(record.fee_agent_amount)

        agent_sum = agent_free + agent_reward + agent_permanent
        if agent_sum != agent_total:
            errors.append(
                f"Agent fee mismatch: {agent_free} + {agent_reward} + {agent_permanent} = {agent_sum} != {agent_total}"
            )

        # Check total amount consistency
        free_amount = to_decimal(record.free_amount)
        reward_amount = to_decimal(record.reward_amount)
        permanent_amount = to_decimal(record.permanent_amount)
        total_amount = to_decimal(record.total_amount)

        total_sum = free_amount + reward_amount + permanent_amount
        if total_sum != total_amount:
            errors.append(
                f"Total amount mismatch: {free_amount} + {reward_amount} + {permanent_amount} = {total_sum} != {total_amount}"
            )

        # Check if all errors are cases where detail sum is 0
        is_zero_sum_error = False
        if errors:
            # Check if all errors are cases where detail sum is 0 but total is not 0
            zero_sum_patterns = [
                "0 + 0 + 0 = 0 !=",  # Pattern for zero sum details
            ]
            is_zero_sum_error = all(
                any(pattern in error for pattern in zero_sum_patterns)
                for error in errors
            )

        return len(errors) == 0, errors, is_zero_sum_error

    async def check_all_records(self, session: AsyncSession, batch_size: int = 1000):
        """Check all credit event records in batches using cursor-based pagination."""
        logger.info("Starting credit event consistency check...")

        # Use cursor-based pagination to avoid batch drift
        last_id = ""
        batch_number = 1

        while True:
            query = (
                select(CreditEventTable)
                .where(CreditEventTable.id > last_id if last_id else True)
                .order_by(CreditEventTable.id)
                .limit(batch_size)
            )

            result = await session.execute(query)
            records = result.fetchall()

            if not records:
                break

            logger.info(
                f"Processing batch {batch_number}, records starting from ID {records[0][0].id}"
            )

            # Update cursor to the last processed record's ID
            last_id = records[-1][0].id

            for record_tuple in records:
                record = record_tuple[0]  # Extract the actual record from tuple
                self.total_records += 1

                is_consistent, errors, is_zero_sum_error = (
                    self.check_record_consistency(record)
                )

                if is_consistent:
                    self.consistent_records += 1
                else:
                    self.inconsistent_records += 1
                    if is_zero_sum_error:
                        # Cases where detail sum is 0, count and store details
                        self.zero_sum_inconsistent_count += 1
                        self.zero_sum_inconsistent_details.append(
                            {
                                "id": record.id,
                                "created_at": record.created_at,
                                "event_type": record.event_type,
                                "errors": errors,
                            }
                        )
                    else:
                        # Unexpected errors where details are non-zero but still unequal, need detailed records
                        self.non_zero_sum_inconsistent_details.append(
                            {
                                "id": record.id,
                                "created_at": record.created_at,
                                "event_type": record.event_type,
                                "errors": errors,
                            }
                        )

            batch_number += 1

        logger.info("Consistency check completed.")

    def print_summary(self):
        """Print summary of the consistency check."""
        print("\n" + "=" * 60)
        print("CREDIT EVENT CONSISTENCY CHECK SUMMARY")
        print("=" * 60)
        print(f"Total records checked: {self.total_records}")
        print(f"Consistent records: {self.consistent_records}")
        print(f"Inconsistent records: {self.inconsistent_records}")
        print(
            f"  - Zero-sum inconsistent (details sum to 0 but total is not 0): {self.zero_sum_inconsistent_count}"
        )
        print(
            f"  - Non-zero-sum inconsistent (unexpected errors): {len(self.non_zero_sum_inconsistent_details)}"
        )

        if self.total_records > 0:
            consistency_rate = (self.consistent_records / self.total_records) * 100
            print(f"Consistency rate: {consistency_rate:.2f}%")

        # Show details for zero-sum inconsistent records
        if self.zero_sum_inconsistent_details:
            print("\n" + "-" * 40)
            print("ZERO-SUM INCONSISTENT RECORDS (Details sum to 0 but total is not 0)")
            print("-" * 40)

            # Show first 10 zero-sum inconsistent records
            for i, detail in enumerate(self.zero_sum_inconsistent_details[:10]):
                print(f"\n{i + 1}. Record ID: {detail['id']}")
                print(f"   Created at: {detail['created_at']}")
                print(f"   Event type: {detail['event_type']}")
                print("   Errors:")
                for error in detail["errors"]:
                    print(f"     - {error}")

            if len(self.zero_sum_inconsistent_details) > 10:
                print(
                    f"\n... and {len(self.zero_sum_inconsistent_details) - 10} more zero-sum inconsistent records."
                )

        # Show details for unexpected errors
        if self.non_zero_sum_inconsistent_details:
            print("\n" + "-" * 40)
            print("NON-ZERO-SUM INCONSISTENT RECORDS (Unexpected Errors)")
            print("-" * 40)

            # Show first 10 non-zero-sum inconsistent records
            for i, detail in enumerate(self.non_zero_sum_inconsistent_details[:10]):
                print(f"\n{i + 1}. Record ID: {detail['id']}")
                print(f"   Created at: {detail['created_at']}")
                print(f"   Event type: {detail['event_type']}")
                print("   Errors:")
                for error in detail["errors"]:
                    print(f"     - {error}")

            if len(self.non_zero_sum_inconsistent_details) > 10:
                print(
                    f"\n... and {len(self.non_zero_sum_inconsistent_details) - 10} more non-zero-sum inconsistent records."
                )

        print("\n" + "=" * 60)


async def main():
    """Main function to run the consistency check."""
    logger.info("Starting CreditEvent consistency check...")

    # Initialize database connection
    await init_db(**config.db)

    checker = CreditEventConsistencyChecker()

    async with get_session() as session:
        await checker.check_all_records(session)

    checker.print_summary()

    logger.info("Consistency check completed.")


if __name__ == "__main__":
    asyncio.run(main())
