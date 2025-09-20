#!/usr/bin/env python3
"""
Diagnostic script to analyze platform_fee account balance inconsistency.

This script performs detailed analysis of the platform_fee account to identify
the source of precision differences between stored balances and calculated balances.
"""

import asyncio
import logging
from decimal import Decimal

from sqlalchemy import select, text

from intentkit.config.config import config
from intentkit.models.credit import (
    DEFAULT_PLATFORM_ACCOUNT_FEE,
    CreditAccount,
    CreditAccountTable,
)
from intentkit.models.db import get_session, init_db

logger = logging.getLogger(__name__)


async def analyze_platform_fee_account():
    """Analyze the platform_fee account balance inconsistency in detail."""

    print("=== Platform Fee Account Balance Analysis ===\n")

    async with get_session() as session:
        # Get the platform_fee account
        account_query = select(CreditAccountTable).where(
            CreditAccountTable.owner_type == "platform",
            CreditAccountTable.owner_id == DEFAULT_PLATFORM_ACCOUNT_FEE,
        )
        account_result = await session.execute(account_query)
        account_row = account_result.scalar_one_or_none()

        if not account_row:
            print("❌ Platform fee account not found!")
            return

        account = CreditAccount.model_validate(account_row)

        print(f"Account ID: {account.id}")
        print(f"Owner: {account.owner_type}:{account.owner_id}")
        print(f"Last Event ID: {account.last_event_id}")
        print(f"Updated At: {account.updated_at}")
        print()

        # Current balances
        print("=== Current Account Balances ===")
        print(f"Free Credits: {account.free_credits}")
        print(f"Reward Credits: {account.reward_credits}")
        print(f"Permanent Credits: {account.credits}")
        total_balance = account.free_credits + account.reward_credits + account.credits
        print(f"Total Balance: {total_balance}")
        print()

        # Calculate expected balances from transactions
        print("=== Transaction-based Balance Calculation ===")

        if account.last_event_id:
            query = text("""
            SELECT 
                COUNT(*) as transaction_count,
                SUM(CASE WHEN ct.credit_debit = 'credit' THEN ct.change_amount ELSE 0 END) as total_credits,
                SUM(CASE WHEN ct.credit_debit = 'debit' THEN ct.change_amount ELSE 0 END) as total_debits,
                SUM(CASE WHEN ct.credit_debit = 'credit' THEN ct.free_amount ELSE -ct.free_amount END) as expected_free_credits,
                SUM(CASE WHEN ct.credit_debit = 'credit' THEN ct.reward_amount ELSE -ct.reward_amount END) as expected_reward_credits,
                SUM(CASE WHEN ct.credit_debit = 'credit' THEN ct.permanent_amount ELSE -ct.permanent_amount END) as expected_permanent_credits
            FROM credit_transactions ct
            JOIN credit_events ce ON ct.event_id = ce.id
            WHERE ct.account_id = :account_id 
              AND ce.id <= :last_event_id
            """)

            params = {
                "account_id": account.id,
                "last_event_id": account.last_event_id,
            }
        else:
            query = text("""
            SELECT 
                COUNT(*) as transaction_count,
                SUM(CASE WHEN ct.credit_debit = 'credit' THEN ct.change_amount ELSE 0 END) as total_credits,
                SUM(CASE WHEN ct.credit_debit = 'debit' THEN ct.change_amount ELSE 0 END) as total_debits,
                SUM(CASE WHEN ct.credit_debit = 'credit' THEN ct.free_amount ELSE -ct.free_amount END) as expected_free_credits,
                SUM(CASE WHEN ct.credit_debit = 'credit' THEN ct.reward_amount ELSE -ct.reward_amount END) as expected_reward_credits,
                SUM(CASE WHEN ct.credit_debit = 'credit' THEN ct.permanent_amount ELSE -ct.permanent_amount END) as expected_permanent_credits
            FROM credit_transactions ct
            WHERE ct.account_id = :account_id
            """)

            params = {"account_id": account.id}

        tx_result = await session.execute(query, params)
        tx_data = tx_result.fetchone()

        transaction_count = tx_data.transaction_count or 0
        total_credits = tx_data.total_credits or Decimal("0")
        total_debits = tx_data.total_debits or Decimal("0")
        expected_free_credits = tx_data.expected_free_credits or Decimal("0")
        expected_reward_credits = tx_data.expected_reward_credits or Decimal("0")
        expected_permanent_credits = tx_data.expected_permanent_credits or Decimal("0")
        expected_total_balance = total_credits - total_debits

        print(f"Total Transactions: {transaction_count}")
        print(f"Total Credits: {total_credits}")
        print(f"Total Debits: {total_debits}")
        print(f"Expected Free Credits: {expected_free_credits}")
        print(f"Expected Reward Credits: {expected_reward_credits}")
        print(f"Expected Permanent Credits: {expected_permanent_credits}")
        print(f"Expected Total Balance: {expected_total_balance}")
        print()

        # Calculate differences
        print("=== Balance Differences ===")
        free_diff = account.free_credits - expected_free_credits
        reward_diff = account.reward_credits - expected_reward_credits
        permanent_diff = account.credits - expected_permanent_credits
        total_diff = total_balance - expected_total_balance

        print(f"Free Credits Difference: {free_diff}")
        print(f"Reward Credits Difference: {reward_diff}")
        print(f"Permanent Credits Difference: {permanent_diff}")
        print(f"Total Balance Difference: {total_diff}")
        print()

        # Check if differences are significant
        tolerance = Decimal("0.0001")
        has_issues = (
            abs(free_diff) > tolerance
            or abs(reward_diff) > tolerance
            or abs(permanent_diff) > tolerance
            or abs(total_diff) > tolerance
        )

        if has_issues:
            print("❌ BALANCE INCONSISTENCY DETECTED!")
            print()

            # Get recent transactions for analysis
            print("=== Recent Transactions Analysis ===")
            recent_tx_query = text("""
            SELECT 
                ct.id,
                ct.event_id,
                ce.created_at,
                ct.credit_debit,
                ct.change_amount,
                ct.free_amount,
                ct.reward_amount,
                ct.permanent_amount,
                ce.event_type,
                ce.note
            FROM credit_transactions ct
            JOIN credit_events ce ON ct.event_id = ce.id
            WHERE ct.account_id = :account_id
            ORDER BY ce.created_at DESC, ct.created_at DESC
            LIMIT 20
            """)

            recent_tx_result = await session.execute(
                recent_tx_query, {"account_id": account.id}
            )
            recent_transactions = recent_tx_result.fetchall()

            print("Last 20 transactions:")
            for tx in recent_transactions:
                sign = "+" if tx.credit_debit == "credit" else "-"
                print(
                    f"  {tx.created_at} | {tx.event_type} | {sign}{tx.change_amount} | "
                    f"F:{tx.free_amount} R:{tx.reward_amount} P:{tx.permanent_amount} | {tx.note}"
                )
            print()

            # Check for precision issues in individual transactions
            print("=== Precision Analysis ===")
            precision_issues = []

            for tx in recent_transactions:
                # Check if the sum of component amounts equals change_amount
                component_sum = (
                    (tx.free_amount or Decimal("0"))
                    + (tx.reward_amount or Decimal("0"))
                    + (tx.permanent_amount or Decimal("0"))
                )

                if abs(component_sum - tx.change_amount) > tolerance:
                    precision_issues.append(
                        {
                            "transaction_id": tx.id,
                            "event_id": tx.event_id,
                            "created_at": tx.created_at,
                            "change_amount": tx.change_amount,
                            "component_sum": component_sum,
                            "difference": component_sum - tx.change_amount,
                        }
                    )

            if precision_issues:
                print(
                    f"Found {len(precision_issues)} transactions with precision issues:"
                )
                for issue in precision_issues:
                    print(
                        f"  TX {issue['transaction_id']}: change_amount={issue['change_amount']}, "
                        f"component_sum={issue['component_sum']}, diff={issue['difference']}"
                    )
            else:
                print("No precision issues found in individual transactions.")
            print()

        else:
            print("✅ No significant balance inconsistencies detected.")
            print()

        # Summary statistics
        print("=== Summary Statistics ===")
        print("Account Statistics:")
        print(f"  Total Income: {account.total_income}")
        print(f"  Total Expense: {account.total_expense}")
        print(
            f"  Net Balance (Income - Expense): {account.total_income - account.total_expense}"
        )
        print(f"  Current Balance: {total_balance}")
        print(
            f"  Difference: {total_balance - (account.total_income - account.total_expense)}"
        )


async def main():
    """Main function to run the platform_fee account analysis."""
    logging.basicConfig(level=logging.INFO)

    # Initialize database
    await init_db(**config.db)

    # Run analysis
    await analyze_platform_fee_account()


if __name__ == "__main__":
    asyncio.run(main())
