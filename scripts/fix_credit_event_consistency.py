#!/usr/bin/env python3
"""
Credit Event Consistency Fixer

This script finds inconsistent credit events and recalculates the 12 detailed amount fields
using the same logic from the expense_skill function, then updates the database records.

The 12 fields that will be recalculated and updated are:
- free_amount, reward_amount, permanent_amount
- fee_platform_free_amount, fee_platform_reward_amount, fee_platform_permanent_amount
- fee_dev_free_amount, fee_dev_reward_amount, fee_dev_permanent_amount
- fee_agent_free_amount, fee_agent_reward_amount, fee_agent_permanent_amount
"""

import asyncio
import logging
import sys
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Tuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

# Add the parent directory to the Python path
sys.path.append("/Users/muninn/crestal/intentkit")

from intentkit.config.config import config
from intentkit.models.credit import CreditEventTable
from intentkit.models.db import get_session, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the precision for all decimal calculations (4 decimal places)
FOURPLACES = Decimal("0.0001")


def to_decimal(value) -> Decimal:
    """Convert value to Decimal, handling None values."""
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


class CreditEventConsistencyFixer:
    """Fixer for credit event consistency issues."""

    def __init__(self):
        self.total_records = 0
        self.inconsistent_records = 0
        self.fixed_records = 0
        self.failed_fixes = 0
        self.inconsistent_details: List[Dict] = []

    def check_record_consistency(
        self, record: CreditEventTable
    ) -> Tuple[bool, List[str]]:
        """Check if a single record is consistent.

        Returns:
            Tuple of (is_consistent, list_of_errors)
        """
        errors = []

        # Convert all amounts to Decimal for precise calculation
        total_amount = to_decimal(record.total_amount)
        fee_platform_amount = to_decimal(record.fee_platform_amount)
        fee_dev_amount = to_decimal(record.fee_dev_amount)
        fee_agent_amount = to_decimal(record.fee_agent_amount)

        # Check detailed amounts for each fee type
        platform_free = to_decimal(record.fee_platform_free_amount)
        platform_reward = to_decimal(record.fee_platform_reward_amount)
        platform_permanent = to_decimal(record.fee_platform_permanent_amount)
        platform_sum = platform_free + platform_reward + platform_permanent

        dev_free = to_decimal(record.fee_dev_free_amount)
        dev_reward = to_decimal(record.fee_dev_reward_amount)
        dev_permanent = to_decimal(record.fee_dev_permanent_amount)
        dev_sum = dev_free + dev_reward + dev_permanent

        agent_free = to_decimal(record.fee_agent_free_amount)
        agent_reward = to_decimal(record.fee_agent_reward_amount)
        agent_permanent = to_decimal(record.fee_agent_permanent_amount)
        agent_sum = agent_free + agent_reward + agent_permanent

        # Check total amounts consistency
        free_amount = to_decimal(record.free_amount)
        reward_amount = to_decimal(record.reward_amount)
        permanent_amount = to_decimal(record.permanent_amount)
        total_sum = free_amount + reward_amount + permanent_amount

        # Check platform fee consistency
        if platform_sum != fee_platform_amount:
            errors.append(
                f"Platform fee mismatch: {platform_free} + {platform_reward} + {platform_permanent} = {platform_sum} != {fee_platform_amount}"
            )

        # Check dev fee consistency
        if dev_sum != fee_dev_amount:
            errors.append(
                f"Dev fee mismatch: {dev_free} + {dev_reward} + {dev_permanent} = {dev_sum} != {fee_dev_amount}"
            )

        # Check agent fee consistency
        if agent_sum != fee_agent_amount:
            errors.append(
                f"Agent fee mismatch: {agent_free} + {agent_reward} + {agent_permanent} = {agent_sum} != {fee_agent_amount}"
            )

        # Check total amount consistency
        if total_sum != total_amount:
            errors.append(
                f"Total amount mismatch: {free_amount} + {reward_amount} + {permanent_amount} = {total_sum} != {total_amount}"
            )

        return len(errors) == 0, errors

    def calculate_detailed_amounts(
        self, record: CreditEventTable
    ) -> Dict[str, Decimal]:
        """Calculate the 12 detailed amount fields using the same logic as expense_skill.

        Returns:
            Dictionary containing the calculated amounts
        """
        # Get the total amounts from the record
        total_amount = to_decimal(record.total_amount)
        fee_platform_amount = to_decimal(record.fee_platform_amount)
        fee_dev_amount = to_decimal(record.fee_dev_amount)
        fee_agent_amount = to_decimal(record.fee_agent_amount)

        # Get the original credit type amounts
        free_amount = to_decimal(record.free_amount)
        reward_amount = to_decimal(record.reward_amount)
        permanent_amount = to_decimal(record.permanent_amount)

        # Calculate fee_platform amounts by credit type
        fee_platform_free_amount = Decimal("0")
        fee_platform_reward_amount = Decimal("0")
        fee_platform_permanent_amount = Decimal("0")

        if fee_platform_amount > Decimal("0") and total_amount > Decimal("0"):
            # Calculate proportions based on the formula
            if free_amount > Decimal("0"):
                fee_platform_free_amount = (
                    free_amount * fee_platform_amount / total_amount
                ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

            if reward_amount > Decimal("0"):
                fee_platform_reward_amount = (
                    reward_amount * fee_platform_amount / total_amount
                ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

            # Calculate permanent amount as the remainder to ensure the sum equals fee_platform_amount
            fee_platform_permanent_amount = (
                fee_platform_amount
                - fee_platform_free_amount
                - fee_platform_reward_amount
            ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

        # Calculate fee_agent amounts by credit type
        fee_agent_free_amount = Decimal("0")
        fee_agent_reward_amount = Decimal("0")
        fee_agent_permanent_amount = Decimal("0")

        if fee_agent_amount > Decimal("0") and total_amount > Decimal("0"):
            # Calculate proportions based on the formula
            if free_amount > Decimal("0"):
                fee_agent_free_amount = (
                    free_amount * fee_agent_amount / total_amount
                ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

            if reward_amount > Decimal("0"):
                fee_agent_reward_amount = (
                    reward_amount * fee_agent_amount / total_amount
                ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

            # Calculate permanent amount as the remainder to ensure the sum equals fee_agent_amount
            fee_agent_permanent_amount = (
                fee_agent_amount - fee_agent_free_amount - fee_agent_reward_amount
            ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

        # Calculate fee_dev amounts by credit type
        fee_dev_free_amount = Decimal("0")
        fee_dev_reward_amount = Decimal("0")
        fee_dev_permanent_amount = Decimal("0")

        if fee_dev_amount > Decimal("0") and total_amount > Decimal("0"):
            # Calculate proportions based on the formula
            if free_amount > Decimal("0"):
                fee_dev_free_amount = (
                    free_amount * fee_dev_amount / total_amount
                ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

            if reward_amount > Decimal("0"):
                fee_dev_reward_amount = (
                    reward_amount * fee_dev_amount / total_amount
                ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

            # Calculate permanent amount as the remainder to ensure the sum equals fee_dev_amount
            fee_dev_permanent_amount = (
                fee_dev_amount - fee_dev_free_amount - fee_dev_reward_amount
            ).quantize(FOURPLACES, rounding=ROUND_HALF_UP)

        return {
            "free_amount": free_amount,
            "reward_amount": reward_amount,
            "permanent_amount": permanent_amount,
            "fee_platform_free_amount": fee_platform_free_amount,
            "fee_platform_reward_amount": fee_platform_reward_amount,
            "fee_platform_permanent_amount": fee_platform_permanent_amount,
            "fee_dev_free_amount": fee_dev_free_amount,
            "fee_dev_reward_amount": fee_dev_reward_amount,
            "fee_dev_permanent_amount": fee_dev_permanent_amount,
            "fee_agent_free_amount": fee_agent_free_amount,
            "fee_agent_reward_amount": fee_agent_reward_amount,
            "fee_agent_permanent_amount": fee_agent_permanent_amount,
        }

    async def fix_inconsistent_record(
        self, session: AsyncSession, record: CreditEventTable
    ) -> bool:
        """Fix a single inconsistent record by recalculating and updating the detailed amounts.

        Returns:
            True if the record was successfully fixed, False otherwise
        """
        try:
            # Calculate the correct detailed amounts
            calculated_amounts = self.calculate_detailed_amounts(record)

            # Update the record with the calculated amounts
            stmt = (
                update(CreditEventTable)
                .where(CreditEventTable.id == record.id)
                .values(**calculated_amounts)
            )
            await session.execute(stmt)

            logger.info(f"Fixed record {record.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to fix record {record.id}: {str(e)}")
            return False

    async def find_and_fix_inconsistent_records(self, session: AsyncSession):
        """Find all inconsistent records and fix them."""
        # Query all credit event records
        stmt = select(CreditEventTable).order_by(CreditEventTable.created_at)
        result = await session.execute(stmt)
        records = result.scalars().all()

        self.total_records = len(records)
        logger.info(f"Total records to check: {self.total_records}")

        batch_size = 100
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            logger.info(
                f"Processing batch {i // batch_size + 1}, records {i + 1}-{min(i + batch_size, len(records))}"
            )

            for record in batch:
                is_consistent, errors = self.check_record_consistency(record)

                if not is_consistent:
                    self.inconsistent_records += 1
                    self.inconsistent_details.append(
                        {
                            "id": record.id,
                            "user_id": record.user_id,
                            "skill_name": record.skill_name,
                            "total_amount": record.total_amount,
                            "errors": errors,
                        }
                    )

                    # Try to fix the record
                    if await self.fix_inconsistent_record(session, record):
                        self.fixed_records += 1
                    else:
                        self.failed_fixes += 1

        # Commit all changes
        await session.commit()
        logger.info("All fixes committed to database.")

    def print_summary(self):
        """Print a summary of the fixing process."""
        print("\n" + "=" * 60)
        print("CREDIT EVENT CONSISTENCY FIXER SUMMARY")
        print("=" * 60)
        print(f"Total records checked: {self.total_records}")
        print(f"Inconsistent records found: {self.inconsistent_records}")
        print(f"Records successfully fixed: {self.fixed_records}")
        print(f"Records failed to fix: {self.failed_fixes}")
        if self.total_records > 0:
            consistency_rate = (
                (self.total_records - self.inconsistent_records)
                / self.total_records
                * 100
            )
            print(f"Original consistency rate: {consistency_rate:.2f}%")
            final_consistency_rate = (
                (self.total_records - self.failed_fixes) / self.total_records * 100
            )
            print(f"Final consistency rate: {final_consistency_rate:.2f}%")
        print("=" * 60)

        # Show details of failed fixes if any
        if self.failed_fixes > 0:
            print("\n" + "-" * 40)
            print("FAILED TO FIX RECORDS")
            print("-" * 40)
            failed_count = 0
            for detail in self.inconsistent_details:
                if failed_count >= self.failed_fixes:
                    break
                print(f"Record ID: {detail['id']}")
                print(f"User ID: {detail['user_id']}")
                print(f"Skill: {detail['skill_name']}")
                print(f"Total Amount: {detail['total_amount']}")
                print("Errors:")
                for error in detail["errors"]:
                    print(f"  - {error}")
                print("-" * 20)
                failed_count += 1


async def main():
    """Main function to run the consistency fixer."""
    logger.info("Starting CreditEvent consistency fixer...")

    # Initialize database connection
    await init_db(**config.db)

    # Create fixer instance
    fixer = CreditEventConsistencyFixer()

    # Run the fixing process
    async with get_session() as session:
        logger.info("Starting credit event consistency fixing...")
        await fixer.find_and_fix_inconsistent_records(session)

    # Print summary
    fixer.print_summary()
    logger.info("Consistency fixing completed.")


if __name__ == "__main__":
    asyncio.run(main())
