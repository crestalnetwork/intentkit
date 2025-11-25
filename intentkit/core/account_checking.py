import asyncio
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text

from intentkit.models.credit import (
    CreditAccount,
    CreditAccountTable,
    CreditEvent,
    CreditEventTable,
    CreditTransaction,
    CreditTransactionTable,
)
from intentkit.models.db import get_session
from intentkit.utils.slack_alert import send_slack_message

logger = logging.getLogger(__name__)


class AccountCheckingResult:
    """Result of an account checking operation."""

    def __init__(
        self, check_type: str, status: bool, details: dict[str, Any] | None = None
    ):
        self.check_type = check_type
        self.status = status  # True if check passed, False if failed
        self.details = details or {}
        self.timestamp = datetime.now(UTC)

    def __str__(self) -> str:
        status_str = "PASSED" if self.status else "FAILED"
        return f"[{self.timestamp.isoformat()}] {self.check_type}: {status_str} - {self.details}"


async def check_account_balance_consistency(
    check_recent_only: bool = True, recent_hours: int = 24
) -> list[AccountCheckingResult]:
    """Check if all account balances are consistent with their transactions.

    This verifies that the total balance in each account matches the sum of all transactions
    for that account, properly accounting for credits and debits.

    To ensure consistency during system operation, this function processes accounts in batches
    using ID-based pagination and uses the last_event_id from each account to limit
    transaction queries, ensuring that only transactions from events up to and including
    the last recorded event for that account are considered.

    Args:
        check_recent_only: If True, only check accounts updated within recent_hours. Default True.
        recent_hours: Number of hours to look back for recent updates. Default 24.

    Returns:
        List of checking results
    """
    results = []
    batch_size = 1000  # Process 1000 accounts at a time
    total_processed = 0
    batch_count = 0
    last_id = ""  # Starting ID for pagination (empty string comes before all valid IDs)

    # Calculate time threshold for recent updates if needed
    time_threshold = None
    if check_recent_only:
        time_threshold = datetime.now(UTC) - timedelta(hours=recent_hours)

    while True:
        # Create a new session for each batch to prevent timeouts
        async with get_session() as session:
            # Get accounts in batches using ID-based pagination
            query = (
                select(CreditAccountTable)
                .where(CreditAccountTable.id > last_id)  # ID-based pagination
                .order_by(CreditAccountTable.id)
                .limit(batch_size)
            )

            # Add time filter if checking recent updates only
            if check_recent_only and time_threshold:
                query = query.where(CreditAccountTable.updated_at >= time_threshold)
            accounts_result = await session.execute(query)
            batch_accounts = [
                CreditAccount.model_validate(acc)
                for acc in accounts_result.scalars().all()
            ]

            # If no more accounts to process, break the loop
            if not batch_accounts:
                break

            # Update counters and last_id for next iteration
            batch_count += 1
            current_batch_size = len(batch_accounts)
            total_processed += current_batch_size
            last_id = batch_accounts[-1].id  # Update last_id for next batch

            logger.info(
                f"Processing account balance batch: {batch_count}, accounts: {current_batch_size}"
            )

            # Process each account in the batch
            for account in batch_accounts:
                # Sleep for 10ms to reduce database load
                await asyncio.sleep(0.01)

                # Calculate the total balance across all credit types
                total_balance = (
                    account.free_credits + account.reward_credits + account.credits
                )

                # Calculate the expected balance from all transactions, regardless of credit type
                # If account has last_event_id, only include transactions from events up to and including that event
                # If no last_event_id, include all transactions for the account
                if account.last_event_id:
                    query = text("""
                    SELECT 
                        SUM(CASE WHEN ct.credit_debit = 'credit' THEN ct.change_amount ELSE 0 END) as credits,
                        SUM(CASE WHEN ct.credit_debit = 'debit' THEN ct.change_amount ELSE 0 END) as debits,
                        SUM(CASE WHEN ct.credit_debit = 'credit' THEN ct.free_amount ELSE -ct.free_amount END) as free_credits_sum,
                        SUM(CASE WHEN ct.credit_debit = 'credit' THEN ct.reward_amount ELSE -ct.reward_amount END) as reward_credits_sum,
                        SUM(CASE WHEN ct.credit_debit = 'credit' THEN ct.permanent_amount ELSE -ct.permanent_amount END) as permanent_credits_sum
                    FROM credit_transactions ct
                    JOIN credit_events ce ON ct.event_id = ce.id
                    WHERE ct.account_id = :account_id 
                      AND ce.id <= :last_event_id
                """)

                    tx_result = await session.execute(
                        query,
                        {
                            "account_id": account.id,
                            "last_event_id": account.last_event_id,
                        },
                    )
                else:
                    query = text("""
                    SELECT 
                        SUM(CASE WHEN ct.credit_debit = 'credit' THEN ct.change_amount ELSE 0 END) as credits,
                        SUM(CASE WHEN ct.credit_debit = 'debit' THEN ct.change_amount ELSE 0 END) as debits,
                        SUM(CASE WHEN ct.credit_debit = 'credit' THEN ct.free_amount ELSE -ct.free_amount END) as free_credits_sum,
                        SUM(CASE WHEN ct.credit_debit = 'credit' THEN ct.reward_amount ELSE -ct.reward_amount END) as reward_credits_sum,
                        SUM(CASE WHEN ct.credit_debit = 'credit' THEN ct.permanent_amount ELSE -ct.permanent_amount END) as permanent_credits_sum
                    FROM credit_transactions ct
                    WHERE ct.account_id = :account_id
                """)

                    tx_result = await session.execute(
                        query,
                        {"account_id": account.id},
                    )
                tx_data = tx_result.fetchone()

                if tx_data is None:
                    credits = Decimal("0")
                    debits = Decimal("0")
                    expected_free_credits = Decimal("0")
                    expected_reward_credits = Decimal("0")
                    expected_permanent_credits = Decimal("0")
                else:
                    credits = tx_data.credits or Decimal("0")
                    debits = tx_data.debits or Decimal("0")
                    expected_free_credits = tx_data.free_credits_sum or Decimal("0")
                    expected_reward_credits = tx_data.reward_credits_sum or Decimal("0")
                    expected_permanent_credits = (
                        tx_data.permanent_credits_sum or Decimal("0")
                    )
                expected_balance = credits - debits

                # Compare total balances and individual credit type balances with tolerance
                tolerance = Decimal("0.01")

                total_balance_diff = abs(total_balance - expected_balance)
                free_credits_diff = abs(account.free_credits - expected_free_credits)
                reward_credits_diff = abs(
                    account.reward_credits - expected_reward_credits
                )
                permanent_credits_diff = abs(
                    account.credits - expected_permanent_credits
                )

                is_total_consistent = total_balance_diff <= tolerance
                is_free_consistent = free_credits_diff <= tolerance
                is_reward_consistent = reward_credits_diff <= tolerance
                is_permanent_consistent = permanent_credits_diff <= tolerance

                is_consistent = (
                    is_total_consistent
                    and is_free_consistent
                    and is_reward_consistent
                    and is_permanent_consistent
                )

                result = AccountCheckingResult(
                    check_type="account_balance_consistency",
                    status=is_consistent,
                    details={
                        "account_id": account.id,
                        "owner_type": account.owner_type,
                        "owner_id": account.owner_id,
                        "current_total_balance": float(total_balance),
                        "free_credits": float(account.free_credits),
                        "reward_credits": float(account.reward_credits),
                        "permanent_credits": float(account.credits),
                        "expected_total_balance": float(expected_balance),
                        "expected_free_credits": float(expected_free_credits),
                        "expected_reward_credits": float(expected_reward_credits),
                        "expected_permanent_credits": float(expected_permanent_credits),
                        "total_credits": float(credits),
                        "total_debits": float(debits),
                        "total_balance_difference": float(
                            total_balance - expected_balance
                        ),
                        "free_credits_difference": float(
                            account.free_credits - expected_free_credits
                        ),
                        "reward_credits_difference": float(
                            account.reward_credits - expected_reward_credits
                        ),
                        "permanent_credits_difference": float(
                            account.credits - expected_permanent_credits
                        ),
                        "is_total_consistent": is_total_consistent,
                        "is_free_consistent": is_free_consistent,
                        "is_reward_consistent": is_reward_consistent,
                        "is_permanent_consistent": is_permanent_consistent,
                        "last_event_id": account.last_event_id,
                        "batch": batch_count,
                        "check_recent_only": check_recent_only,
                        "recent_hours": recent_hours if check_recent_only else None,
                    },
                )
                results.append(result)

                if not is_consistent:
                    inconsistency_details = []
                    if not is_total_consistent:
                        inconsistency_details.append(
                            f"Total: {total_balance} vs {expected_balance}"
                        )
                    if not is_free_consistent:
                        inconsistency_details.append(
                            f"Free: {account.free_credits} vs {expected_free_credits}"
                        )
                    if not is_reward_consistent:
                        inconsistency_details.append(
                            f"Reward: {account.reward_credits} vs {expected_reward_credits}"
                        )
                    if not is_permanent_consistent:
                        inconsistency_details.append(
                            f"Permanent: {account.credits} vs {expected_permanent_credits}"
                        )

                    logger.warning(
                        f"Account balance inconsistency detected: {account.id} ({account.owner_type}:{account.owner_id}) - "
                        f"{'; '.join(inconsistency_details)}"
                    )

    filter_info = (
        f" (recent {recent_hours}h only)" if check_recent_only else " (all accounts)"
    )
    logger.info(
        f"Completed account balance consistency check{filter_info}: processed {total_processed} accounts in {batch_count} batches"
    )

    return results


async def check_transaction_balance() -> list[AccountCheckingResult]:
    """Check if all credit events have balanced transactions.

    For each credit event, the sum of all credit transactions should equal the sum of all debit transactions.
    Events are processed in batches to prevent memory overflow issues using ID-based pagination for better performance.

    Returns:
        List of checking results
    """
    results = []
    batch_size = 1000  # Process 1000 events at a time
    total_processed = 0
    batch_count = 0
    last_id = ""  # Starting ID for pagination (empty string comes before all valid IDs)

    # Time window for events (last 3 days for performance)
    three_days_ago = datetime.now(UTC) - timedelta(hours=4)

    while True:
        # Create a new session for each batch to prevent timeouts
        async with get_session() as session:
            # Get events in batches using ID-based pagination
            query = (
                select(CreditEventTable)
                .where(CreditEventTable.created_at >= three_days_ago)
                .where(
                    CreditEventTable.id > last_id
                )  # Key change: ID-based pagination with string comparison
                .order_by(CreditEventTable.id)
                .limit(batch_size)
            )
            events_result = await session.execute(query)
            batch_events = [
                CreditEvent.model_validate(event)
                for event in events_result.scalars().all()
            ]

            # If no more events to process, break the loop
            if not batch_events:
                break

            # Update counters and last_id for next iteration
            batch_count += 1
            current_batch_size = len(batch_events)
            total_processed += current_batch_size
            last_id = batch_events[-1].id  # Update last_id for next batch

            logger.info(
                f"Processing transaction balance batch: {batch_count}, events: {current_batch_size}"
            )

            # Process each event in the batch
            for event in batch_events:
                # Sleep for 10ms to reduce database load
                await asyncio.sleep(0.01)

                # Get all transactions for this event
                tx_query = select(CreditTransactionTable).where(
                    CreditTransactionTable.event_id == event.id
                )
                tx_result = await session.execute(tx_query)
                transactions = [
                    CreditTransaction.model_validate(tx)
                    for tx in tx_result.scalars().all()
                ]

                # Calculate credit and debit sums
                credit_sum = sum(
                    tx.change_amount
                    for tx in transactions
                    if tx.credit_debit == "credit"
                )
                debit_sum = sum(
                    tx.change_amount
                    for tx in transactions
                    if tx.credit_debit == "debit"
                )

                # Check if they balance
                is_balanced = credit_sum == debit_sum

                result = AccountCheckingResult(
                    check_type="transaction_balance",
                    status=is_balanced,
                    details={
                        "event_id": event.id,
                        "event_type": event.event_type,
                        "credit_sum": float(credit_sum),
                        "debit_sum": float(debit_sum),
                        "difference": float(credit_sum - debit_sum),
                        "created_at": event.created_at.isoformat()
                        if event.created_at
                        else None,
                        "batch": batch_count,
                    },
                )
                results.append(result)

                if not is_balanced:
                    logger.warning(
                        f"Transaction imbalance detected for event {event.id} ({event.event_type}). "
                        f"Credit: {credit_sum}, Debit: {debit_sum}"
                    )

    logger.info(
        f"Completed transaction balance check: processed {total_processed} events in {batch_count} batches"
    )

    return results


async def check_orphaned_transactions() -> list[AccountCheckingResult]:
    """Check for orphaned transactions that don't have a corresponding event.

    Returns:
        List of checking results
    """
    # Create a new session for this function
    async with get_session() as session:
        # Find transactions with event_ids that don't exist in the events table
        query = text("""
        SELECT t.id, t.account_id, t.event_id, t.tx_type, t.credit_debit, t.change_amount, t.credit_type, t.created_at
        FROM credit_transactions t
        LEFT JOIN credit_events e ON t.event_id = e.id
        WHERE e.id IS NULL
    """)

        result = await session.execute(query)
        orphaned_txs = result.fetchall()

        # Process orphaned transactions with a sleep to reduce database load
        orphaned_tx_details = []
        for tx in orphaned_txs[:100]:  # Limit to first 100 for report size
            # Sleep for 10ms to reduce database load
            await asyncio.sleep(0.01)

            # Add transaction details to the list
            orphaned_tx_details.append(
                {
                    "id": tx.id,
                    "account_id": tx.account_id,
                    "event_id": tx.event_id,
                    "tx_type": tx.tx_type,
                    "credit_debit": tx.credit_debit,
                    "change_amount": float(tx.change_amount),
                    "credit_type": tx.credit_type,
                    "created_at": tx.created_at.isoformat() if tx.created_at else None,
                }
            )

        check_result = AccountCheckingResult(
            check_type="orphaned_transactions",
            status=(len(orphaned_txs) == 0),
            details={
                "orphaned_count": len(orphaned_txs),
                "orphaned_transactions": orphaned_tx_details,
            },
        )

        if orphaned_txs:
            logger.warning(
                f"Found {len(orphaned_txs)} orphaned transactions without corresponding events"
            )

    return [check_result]


async def check_orphaned_events() -> list[AccountCheckingResult]:
    """Check for orphaned events that don't have any transactions.

    Returns:
        List of checking results
    """
    # Create a new session for this function
    async with get_session() as session:
        # Find events that don't have any transactions
        query = text("""
        SELECT e.id, e.event_type, e.account_id, e.total_amount, e.credit_type, e.created_at
        FROM credit_events e
        LEFT JOIN credit_transactions t ON e.id = t.event_id
        WHERE t.id IS NULL
    """)

        result = await session.execute(query)
        orphaned_events = result.fetchall()

        if not orphaned_events:
            return [
                AccountCheckingResult(
                    check_type="orphaned_events",
                    status=True,
                    details={"message": "No orphaned events found"},
                )
            ]

        # If we found orphaned events, report them
        orphaned_event_ids = [event.id for event in orphaned_events]
        orphaned_event_details = []
        for event in orphaned_events:
            # Sleep for 10ms to reduce database load
            await asyncio.sleep(0.01)

            # Add event details to the list
            orphaned_event_details.append(
                {
                    "event_id": event.id,
                    "event_type": event.event_type,
                    "account_id": event.account_id,
                    "total_amount": float(event.total_amount),
                    "credit_type": event.credit_type,
                    "created_at": event.created_at.isoformat()
                    if event.created_at
                    else None,
                }
            )

        logger.warning(
            f"Found {len(orphaned_events)} orphaned events with no transactions: {orphaned_event_ids}"
        )

        return [
            AccountCheckingResult(
                check_type="orphaned_events",
                status=False,
                details={
                    "orphaned_count": len(orphaned_events),
                    "orphaned_events": orphaned_event_details,
                },
            )
        ]


async def check_total_credit_balance() -> list[AccountCheckingResult]:
    """Check if the sum of all free_credits, reward_credits, and credits across all accounts is 0.

    This verifies that the overall credit system is balanced, with all credits accounted for.

    Returns:
        List of checking results
    """
    # Create a new session for this function
    async with get_session() as session:
        # Query to sum all credit types across all accounts
        query = text("""
        SELECT 
            SUM(free_credits) as total_free_credits,
            SUM(reward_credits) as total_reward_credits,
            SUM(credits) as total_permanent_credits,
            SUM(free_credits) + SUM(reward_credits) + SUM(credits) as grand_total
        FROM credit_accounts
    """)

        result = await session.execute(query)
        balance_data = result.fetchone()

        total_free_credits = balance_data.total_free_credits or Decimal("0")
        total_reward_credits = balance_data.total_reward_credits or Decimal("0")
        total_permanent_credits = balance_data.total_permanent_credits or Decimal("0")
        grand_total = balance_data.grand_total or Decimal("0")

        # Check if the grand total is zero (or very close to zero due to potential floating point issues)
        is_balanced = grand_total == Decimal("0")

        # If not exactly zero but very close (due to potential rounding issues), log a warning but still consider it balanced
        if not is_balanced and abs(grand_total) < Decimal("0.01"):
            logger.warning(
                f"Total credit balance is very close to zero but not exact: {grand_total}. "
                f"This might be due to rounding issues."
            )
            is_balanced = True

        result = AccountCheckingResult(
            check_type="total_credit_balance",
            status=is_balanced,
            details={
                "total_free_credits": float(total_free_credits),
                "total_reward_credits": float(total_reward_credits),
                "total_permanent_credits": float(total_permanent_credits),
                "grand_total": float(grand_total),
            },
        )

        if not is_balanced:
            logger.warning(
                f"Total credit balance inconsistency detected. System is not balanced. "
                f"Total: {grand_total} (Free: {total_free_credits}, Reward: {total_reward_credits}, "
                f"Permanent: {total_permanent_credits})"
            )

    return [result]


async def check_transaction_total_balance() -> list[AccountCheckingResult]:
    """Check if the total credit and debit amounts in the CreditTransaction table are balanced.

    This verifies that across all transactions in the system, the total credits equal the total debits.

    Returns:
        List of checking results
    """
    # Create a new session for this function
    async with get_session() as session:
        # Query to sum all credit and debit transactions
        query = text("""
        SELECT 
            SUM(CASE WHEN credit_debit = 'credit' THEN change_amount ELSE 0 END) as total_credits,
            SUM(CASE WHEN credit_debit = 'debit' THEN change_amount ELSE 0 END) as total_debits
        FROM credit_transactions
    """)

        result = await session.execute(query)
        balance_data = result.fetchone()

        total_credits = balance_data.total_credits or Decimal("0")
        total_debits = balance_data.total_debits or Decimal("0")
        difference = total_credits - total_debits

        # Check if credits and debits are balanced (difference should be zero)
        is_balanced = difference == Decimal("0")

        # If not exactly zero but very close (due to potential rounding issues), log a warning but still consider it balanced
        if not is_balanced and abs(difference) < Decimal("0.001"):
            logger.warning(
                f"Transaction total balance is very close to zero but not exact: {difference}. "
                f"This might be due to rounding issues."
            )
            is_balanced = True

        result = AccountCheckingResult(
            check_type="transaction_total_balance",
            status=is_balanced,
            details={
                "total_credits": float(total_credits),
                "total_debits": float(total_debits),
                "difference": float(difference),
            },
        )

        if not is_balanced:
            logger.warning(
                f"Transaction total balance inconsistency detected. System is not balanced. "
                f"Credits: {total_credits}, Debits: {total_debits}, Difference: {difference}"
            )

    return [result]


async def run_quick_checks() -> dict[str, list[AccountCheckingResult]]:
    """Run quick account checking procedures and return results.

    These checks are designed to be fast and can be run frequently.

    Returns:
        Dictionary mapping check names to their results
    """
    logger.info("Starting quick account checking procedures")

    results = {}
    # Quick checks don't need a session at this level as each function creates its own session
    results["transaction_balance"] = await check_transaction_balance()
    results["orphaned_transactions"] = await check_orphaned_transactions()
    results["orphaned_events"] = await check_orphaned_events()
    results["total_credit_balance"] = await check_total_credit_balance()
    results["transaction_total_balance"] = await check_transaction_total_balance()

    # Log summary
    all_passed = True
    failed_count = 0
    for check_name, check_results in results.items():
        check_failed_count = sum(1 for result in check_results if not result.status)
        failed_count += check_failed_count

        if check_failed_count > 0:
            logger.warning(
                f"{check_name}: {check_failed_count} of {len(check_results)} checks failed"
            )
            all_passed = False
        else:
            logger.info(f"{check_name}: All {len(check_results)} checks passed")

    if all_passed:
        logger.info("All quick account checks passed successfully")
    else:
        logger.warning(
            f"Quick account checking summary: {failed_count} checks failed - see logs for details"
        )

    # Create a summary message with color based on status
    total_checks = sum(len(check_results) for check_results in results.values())

    if all_passed:
        color = "good"  # Green color
        title = "✅ Quick Account Checking Completed Successfully"
        text = f"All {total_checks} quick account checks passed successfully."
        notify = ""  # No notification needed for success
    else:
        color = "danger"  # Red color
        title = "❌ Quick Account Checking Found Issues"
        text = f"Quick account checking found {failed_count} issues out of {total_checks} checks."
        notify = "<!channel> "  # Notify channel for failures

    # Create attachments with check details
    attachments = [{"color": color, "title": title, "text": text, "fields": []}]

    # Add fields for each check type
    for check_name, check_results in results.items():
        check_failed_count = sum(1 for result in check_results if not result.status)
        check_status = (
            "✅ Passed"
            if check_failed_count == 0
            else f"❌ Failed ({check_failed_count} issues)"
        )

        attachments[0]["fields"].append(
            {
                "title": check_name.replace("_", " ").title(),
                "value": check_status,
                "short": True,
            }
        )

    # Send the message
    send_slack_message(
        message=f"{notify}Quick Account Checking Results", attachments=attachments
    )

    return results


async def run_slow_checks() -> dict[str, list[AccountCheckingResult]]:
    """Run slow account checking procedures and return results.

    These checks are more resource-intensive and should be run less frequently.

    Returns:
        Dictionary mapping check names to their results
    """
    logger.info("Starting slow account checking procedures")

    results = {}
    # Slow checks don't need a session at this level as each function creates its own session
    results["account_balance"] = await check_account_balance_consistency()

    # Log summary
    all_passed = True
    failed_count = 0
    for check_name, check_results in results.items():
        check_failed_count = sum(1 for result in check_results if not result.status)
        failed_count += check_failed_count

        if check_failed_count > 0:
            logger.warning(
                f"{check_name}: {check_failed_count} of {len(check_results)} checks failed"
            )
            all_passed = False
        else:
            logger.info(f"{check_name}: All {len(check_results)} checks passed")

    if all_passed:
        logger.info("All slow account checks passed successfully")
    else:
        logger.warning(
            f"Slow account checking summary: {failed_count} checks failed - see logs for details"
        )

    # Send summary to Slack

    # Create a summary message with color based on status
    total_checks = sum(len(check_results) for check_results in results.values())

    if all_passed:
        color = "good"  # Green color
        title = "✅ Slow Account Checking Completed Successfully"
        text = f"All {total_checks} slow account checks passed successfully."
        notify = ""  # No notification needed for success
    else:
        color = "danger"  # Red color
        title = "❌ Slow Account Checking Found Issues"
        text = f"Slow account checking found {failed_count} issues out of {total_checks} checks."
        notify = "<!channel> "  # Notify channel for failures

    # Create attachments with check details
    attachments = [{"color": color, "title": title, "text": text, "fields": []}]

    # Add fields for each check type
    for check_name, check_results in results.items():
        check_failed_count = sum(1 for result in check_results if not result.status)
        check_status = (
            "✅ Passed"
            if check_failed_count == 0
            else f"❌ Failed ({check_failed_count} issues)"
        )

        attachments[0]["fields"].append(
            {
                "title": check_name.replace("_", " ").title(),
                "value": check_status,
                "short": True,
            }
        )

    # If there are failed account balance checks, add details of first 5 failed accounts
    if "account_balance" in results:
        failed_account_results = [r for r in results["account_balance"] if not r.status]
        if failed_account_results:
            # Add a separate attachment for failed account details
            failed_details_text = "First 5 inconsistent accounts:\n"
            for i, result in enumerate(failed_account_results[:5]):
                details = result.details
                failed_details_text += (
                    f"{i + 1}. Account {details['account_id']} ({details['owner_type']}:{details['owner_id']}):\n"
                    f"   • Total: {details['current_total_balance']:.4f} vs {details['expected_total_balance']:.4f} (diff: {details['total_balance_difference']:.4f})\n"
                    f"   • Free: {details['free_credits']:.4f} vs {details['expected_free_credits']:.4f} (diff: {details['free_credits_difference']:.4f})\n"
                    f"   • Reward: {details['reward_credits']:.4f} vs {details['expected_reward_credits']:.4f} (diff: {details['reward_credits_difference']:.4f})\n"
                    f"   • Permanent: {details['permanent_credits']:.4f} vs {details['expected_permanent_credits']:.4f} (diff: {details['permanent_credits_difference']:.4f})\n"
                )

            attachments.append(
                {
                    "color": "warning",
                    "title": "Account Balance Inconsistencies Details",
                    "text": failed_details_text,
                    "mrkdwn_in": ["text"],
                }
            )

    # Send the message
    send_slack_message(
        message=f"{notify}Slow Account Checking Results", attachments=attachments
    )

    return results
