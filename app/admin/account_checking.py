import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.config import config
from models.credit import (
    CreditAccount,
    CreditAccountTable,
    CreditEvent,
    CreditEventTable,
    CreditTransaction,
    CreditTransactionTable,
)
from models.db import get_session, init_db

logger = logging.getLogger(__name__)


class AccountCheckingResult:
    """Result of an account checking operation."""

    def __init__(self, check_type: str, status: bool, details: Optional[Dict] = None):
        self.check_type = check_type
        self.status = status  # True if check passed, False if failed
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc)

    def __str__(self) -> str:
        status_str = "PASSED" if self.status else "FAILED"
        return f"[{self.timestamp.isoformat()}] {self.check_type}: {status_str} - {self.details}"


async def check_account_balance_consistency(
    session: AsyncSession,
) -> List[AccountCheckingResult]:
    """Check if all account balances are consistent with their transactions.

    This verifies that the total balance in each account matches the sum of all transactions
    for that account, properly accounting for credits and debits.

    To ensure consistency during system operation, this function uses the maximum updated_at
    timestamp from all accounts to limit transaction queries, ensuring that only transactions
    created before or at the same time as the account snapshot are considered.

    Args:
        session: Database session

    Returns:
        List of checking results
    """
    results = []

    # Get all accounts
    query = select(CreditAccountTable)
    accounts_result = await session.execute(query)
    accounts = [
        CreditAccount.model_validate(acc) for acc in accounts_result.scalars().all()
    ]

    # Find the maximum updated_at timestamp from all accounts
    # This represents the point in time when we took the snapshot of account balances
    max_updated_at = (
        max([account.updated_at for account in accounts]) if accounts else None
    )

    if not max_updated_at:
        return results

    for account in accounts:
        # Sleep for 10ms to reduce database load
        await asyncio.sleep(0.01)

        # Calculate the total balance across all credit types
        total_balance = account.free_credits + account.reward_credits + account.credits

        # Calculate the expected balance from all transactions, regardless of credit type
        # Only include transactions created before or at the same time as the account snapshot
        query = text("""
            SELECT 
                SUM(CASE WHEN credit_debit = 'credit' THEN change_amount ELSE 0 END) as credits,
                SUM(CASE WHEN credit_debit = 'debit' THEN change_amount ELSE 0 END) as debits
            FROM credit_transactions
            WHERE account_id = :account_id 
              AND created_at <= :max_updated_at
        """)

        tx_result = await session.execute(
            query, {"account_id": account.id, "max_updated_at": max_updated_at}
        )
        tx_data = tx_result.fetchone()

        credits = tx_data.credits or Decimal("0")
        debits = tx_data.debits or Decimal("0")
        expected_balance = credits - debits

        # Compare total balances
        is_consistent = total_balance == expected_balance

        result = AccountCheckingResult(
            check_type="account_total_balance",
            status=is_consistent,
            details={
                "account_id": account.id,
                "owner_type": account.owner_type,
                "owner_id": account.owner_id,
                "current_total_balance": float(total_balance),
                "free_credits": float(account.free_credits),
                "reward_credits": float(account.reward_credits),
                "credits": float(account.credits),
                "expected_balance": float(expected_balance),
                "total_credits": float(credits),
                "total_debits": float(debits),
                "difference": float(total_balance - expected_balance),
                "max_updated_at": max_updated_at.isoformat()
                if max_updated_at
                else None,
            },
        )
        results.append(result)

        if not is_consistent:
            logger.warning(
                f"Account total balance inconsistency detected: {account.id} ({account.owner_type}:{account.owner_id}) "
                f"Current total: {total_balance}, Expected: {expected_balance}"
            )

    return results


async def check_transaction_balance(
    session: AsyncSession,
) -> List[AccountCheckingResult]:
    """Check if all credit events have balanced transactions.

    For each credit event, the sum of all credit transactions should equal the sum of all debit transactions.

    Args:
        session: Database session

    Returns:
        List of checking results
    """
    results = []

    # Get all events from the last 3 days (limit to recent events for performance)
    three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
    query = select(CreditEventTable).where(
        CreditEventTable.created_at >= three_days_ago
    )
    events_result = await session.execute(query)
    events = [
        CreditEvent.model_validate(event) for event in events_result.scalars().all()
    ]

    for event in events:
        # Sleep for 10ms to reduce database load
        await asyncio.sleep(0.01)

        # Get all transactions for this event
        tx_query = select(CreditTransactionTable).where(
            CreditTransactionTable.event_id == event.id
        )
        tx_result = await session.execute(tx_query)
        transactions = [
            CreditTransaction.model_validate(tx) for tx in tx_result.scalars().all()
        ]

        # Calculate credit and debit sums
        credit_sum = sum(
            tx.change_amount for tx in transactions if tx.credit_debit == "credit"
        )
        debit_sum = sum(
            tx.change_amount for tx in transactions if tx.credit_debit == "debit"
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
            },
        )
        results.append(result)

        if not is_balanced:
            logger.warning(
                f"Transaction imbalance detected for event {event.id} ({event.event_type}). "
                f"Credit: {credit_sum}, Debit: {debit_sum}"
            )

    return results


async def check_orphaned_transactions(
    session: AsyncSession,
) -> List[AccountCheckingResult]:
    """Check for orphaned transactions that don't have a corresponding event.

    Args:
        session: Database session

    Returns:
        List of checking results
    """
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


async def check_orphaned_events(session: AsyncSession) -> List[AccountCheckingResult]:
    """Check for orphaned events that don't have any transactions.

    Args:
        session: Database session

    Returns:
        List of checking results
    """
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


async def check_total_credit_balance(
    session: AsyncSession,
) -> List[AccountCheckingResult]:
    """Check if the sum of all free_credits, reward_credits, and credits across all accounts is 0.

    This verifies that the overall credit system is balanced, with all credits accounted for.

    Args:
        session: Database session

    Returns:
        List of checking results
    """
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
    if not is_balanced and abs(grand_total) < Decimal("0.001"):
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


async def check_transaction_total_balance(
    session: AsyncSession,
) -> List[AccountCheckingResult]:
    """Check if the total credit and debit amounts in the CreditTransaction table are balanced.

    This verifies that across all transactions in the system, the total credits equal the total debits.

    Args:
        session: Database session

    Returns:
        List of checking results
    """
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


async def run_all_checks() -> Dict[str, List[AccountCheckingResult]]:
    """Run all account checking procedures and return results.

    Returns:
        Dictionary mapping check names to their results
    """
    logger.info("Starting account checking procedures")

    results = {}
    async with get_session() as session:
        # Run all checks
        results["account_balance"] = await check_account_balance_consistency(session)
        results["transaction_balance"] = await check_transaction_balance(session)
        results["orphaned_transactions"] = await check_orphaned_transactions(session)
        results["orphaned_events"] = await check_orphaned_events(session)
        results["total_credit_balance"] = await check_total_credit_balance(session)
        results["transaction_total_balance"] = await check_transaction_total_balance(
            session
        )

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
        logger.info("All account checks passed successfully")
    else:
        logger.warning(
            f"Account checking summary: {failed_count} checks failed - see logs for details"
        )

    # Send summary to Slack
    from utils.slack_alert import send_slack_message

    # Create a summary message with color based on status
    total_checks = sum(len(check_results) for check_results in results.values())

    if all_passed:
        color = "good"  # Green color
        title = "✅ Account Checking Completed Successfully"
        text = f"All {total_checks} account checks passed successfully."
        notify = ""  # No notification needed for success
    else:
        color = "danger"  # Red color
        title = "❌ Account Checking Found Issues"
        text = f"Account checking found {failed_count} issues out of {total_checks} checks."
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
        message=f"{notify}Account Checking Results", attachments=attachments
    )

    return results


async def main():
    await init_db(**config.db)
    """Main entry point for running account checks."""
    logger.info("Starting account checking procedures")
    results = await run_all_checks()
    logger.info("Completed account checking procedures")
    return results


if __name__ == "__main__":
    import asyncio

    # Run the main function
    asyncio.run(main())
