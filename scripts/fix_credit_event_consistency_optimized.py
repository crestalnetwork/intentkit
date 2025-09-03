#!/usr/bin/env python3
"""
Optimized Credit Event Consistency Fixer

This is an optimized version of the credit event consistency fixer that addresses
performance bottlenecks in the original script:

1. Uses streaming/pagination instead of loading all records into memory
2. Implements batch updates for better database performance
3. Uses smaller transaction scopes to avoid long-running transactions
4. Adds concurrent processing for CPU-intensive calculations
5. Optimizes database queries with proper indexing hints

The 12 fields that will be recalculated and updated are:
- free_amount, reward_amount, permanent_amount
- fee_platform_free_amount, fee_platform_reward_amount, fee_platform_permanent_amount
- fee_dev_free_amount, fee_dev_reward_amount, fee_dev_permanent_amount
- fee_agent_free_amount, fee_agent_reward_amount, fee_agent_permanent_amount
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.config import config
from intentkit.models.credit import CreditEventTable
from intentkit.models.db import get_session, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the precision for all decimal calculations (4 decimal places)
FOURPLACES = Decimal("0.0001")

# Configuration for optimization
PAGE_SIZE = 1000  # Larger page size for streaming
BATCH_UPDATE_SIZE = 50  # Batch size for database updates
MAX_WORKERS = 4  # Number of threads for concurrent processing
COMMIT_INTERVAL = 10  # Commit every N batches


def to_decimal(value) -> Decimal:
    """Convert value to Decimal, handling None values."""
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


class OptimizedCreditEventConsistencyFixer:
    """Optimized fixer for credit event consistency issues."""

    def __init__(self):
        self.total_records = 0
        self.inconsistent_records = 0
        self.fixed_records = 0
        self.failed_fixes = 0
        self.processed_batches = 0
        self.start_time = time.time()
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

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
        
        # Special handling for records where credit type amounts are 0
        # but total_amount is non-zero - distribute total_amount based on credit_type
        if (total_amount > Decimal("0") and 
            free_amount == Decimal("0") and 
            reward_amount == Decimal("0") and 
            permanent_amount == Decimal("0")):
            
            # Determine which credit type to use for distribution
            credit_type = None
            if hasattr(record, 'credit_type') and record.credit_type:
                credit_type = record.credit_type
            elif hasattr(record, 'credit_types') and record.credit_types and len(record.credit_types) > 0:
                credit_type = record.credit_types[0]
            
            # Distribute total_amount to the appropriate credit type field using CreditType enum values
            if credit_type == "free_credits":  # CreditType.FREE
                free_amount = total_amount
            elif credit_type == "reward_credits":  # CreditType.REWARD
                reward_amount = total_amount
            elif credit_type == "credits":  # CreditType.PERMANENT
                permanent_amount = total_amount
            else:
                raise ValueError(f"Unknown or missing credit_type: {credit_type} for record {record.id} with total_amount > 0 but all credit fields are 0")

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

    async def process_records_batch(
        self, session: AsyncSession, records: List[CreditEventTable]
    ) -> Tuple[List[Dict], int, int]:
        """Process a batch of records and return updates to be applied.

        Returns:
            Tuple of (updates_list, fixed_count, failed_count)
        """
        updates = []
        fixed_count = 0
        failed_count = 0

        # Use thread pool for CPU-intensive consistency checking and calculations
        loop = asyncio.get_event_loop()

        # Process records concurrently
        tasks = []
        for record in records:
            task = loop.run_in_executor(
                self.executor, self._process_single_record, record
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to process record {records[i].id}: {result}")
                failed_count += 1
            elif result is not None:
                updates.append({"id": records[i].id, **result})
                fixed_count += 1

        return updates, fixed_count, failed_count

    def _process_single_record(self, record: CreditEventTable) -> Optional[Dict]:
        """Process a single record (CPU-intensive part).

        Returns:
            Dictionary of updates if record needs fixing, None if consistent
        """
        try:
            is_consistent, _ = self.check_record_consistency(record)
            if not is_consistent:
                return self.calculate_detailed_amounts(record)
            return None
        except Exception as e:
            raise Exception(f"Error processing record {record.id}: {str(e)}")

    async def batch_update_records(
        self, session: AsyncSession, updates: List[Dict]
    ) -> Tuple[int, int]:
        """Apply batch updates to the database.

        Returns:
            Tuple of (successful_updates, failed_updates)
        """
        successful = 0
        failed = 0

        # Process updates in smaller batches to avoid large transactions
        for i in range(0, len(updates), BATCH_UPDATE_SIZE):
            batch_updates = updates[i : i + BATCH_UPDATE_SIZE]

            try:
                # Use bulk update for better performance
                for update_data in batch_updates:
                    record_id = update_data.pop("id")
                    stmt = (
                        update(CreditEventTable)
                        .where(CreditEventTable.id == record_id)
                        .values(**update_data)
                    )
                    await session.execute(stmt)

                successful += len(batch_updates)

            except Exception as e:
                logger.error(f"Failed to update batch: {str(e)}")
                failed += len(batch_updates)

        return successful, failed

    async def get_total_count(self, session: AsyncSession) -> int:
        """Get total count of records efficiently."""
        stmt = select(text("COUNT(*)")).select_from(CreditEventTable)
        result = await session.execute(stmt)
        return result.scalar()

    async def stream_records(self, session: AsyncSession, offset: int, limit: int):
        """Stream records in pages to avoid loading all into memory."""
        stmt = (
            select(CreditEventTable)
            .order_by(CreditEventTable.created_at)
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def find_and_fix_inconsistent_records(self, session: AsyncSession):
        """Find all inconsistent records and fix them using optimized approach."""
        # Get total count first
        self.total_records = await self.get_total_count(session)
        logger.info(f"Total records to check: {self.total_records}")

        offset = 0
        batch_number = 1
        pending_updates = []

        while offset < self.total_records:
            # Stream records in pages
            records = await self.stream_records(session, offset, PAGE_SIZE)

            if not records:
                break

            logger.info(
                f"Processing batch {batch_number}, records {offset + 1}-{min(offset + PAGE_SIZE, self.total_records)}"
            )

            # Process batch concurrently
            updates, fixed_count, failed_count = await self.process_records_batch(
                session, records
            )

            # Accumulate updates
            pending_updates.extend(updates)
            self.inconsistent_records += len(updates) + failed_count
            self.failed_fixes += failed_count

            # Apply updates in batches and commit periodically
            if (
                len(pending_updates) >= BATCH_UPDATE_SIZE
                or batch_number % COMMIT_INTERVAL == 0
            ):
                if pending_updates:
                    successful, failed = await self.batch_update_records(
                        session, pending_updates
                    )
                    self.fixed_records += successful
                    self.failed_fixes += failed

                    # Commit periodically to avoid long transactions
                    await session.commit()
                    logger.info(f"Committed {successful} updates, {failed} failed")

                    pending_updates = []

            if fixed_count > 0 or failed_count > 0:
                logger.info(
                    f"Batch {batch_number} completed: {fixed_count} to fix, {failed_count} failed"
                )

            offset += PAGE_SIZE
            batch_number += 1
            self.processed_batches += 1

        # Apply any remaining updates
        if pending_updates:
            successful, failed = await self.batch_update_records(
                session, pending_updates
            )
            self.fixed_records += successful
            self.failed_fixes += failed
            await session.commit()
            logger.info(f"Final commit: {successful} updates, {failed} failed")

        logger.info("All fixes committed to database.")

    def print_summary(self):
        """Print a summary of the fixing process."""
        elapsed_time = time.time() - self.start_time

        print("\n" + "=" * 60)
        print("OPTIMIZED CREDIT EVENT CONSISTENCY FIXER SUMMARY")
        print("=" * 60)
        print(f"Total records checked: {self.total_records}")
        print(f"Inconsistent records found: {self.inconsistent_records}")
        print(f"Records successfully fixed: {self.fixed_records}")
        print(f"Records failed to fix: {self.failed_fixes}")
        print(f"Processed batches: {self.processed_batches}")
        print(f"Total processing time: {elapsed_time:.2f} seconds")

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

            records_per_second = (
                self.total_records / elapsed_time if elapsed_time > 0 else 0
            )
            print(f"Processing rate: {records_per_second:.2f} records/second")

        print("=" * 60)

    def __del__(self):
        """Cleanup thread pool executor."""
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=True)


async def main():
    """Main function to run the optimized consistency fixer."""
    logger.info("Starting Optimized CreditEvent consistency fixer...")

    # Initialize database connection
    await init_db(**config.db)

    # Create fixer instance
    fixer = OptimizedCreditEventConsistencyFixer()

    try:
        # Run the fixing process
        async with get_session() as session:
            logger.info("Starting credit event consistency fixing...")
            await fixer.find_and_fix_inconsistent_records(session)

        # Print summary
        fixer.print_summary()
        logger.info("Consistency fixing completed.")

    except Exception as e:
        logger.error(f"Error during processing: {str(e)}")
        raise
    finally:
        # Ensure cleanup
        del fixer


if __name__ == "__main__":
    asyncio.run(main())
