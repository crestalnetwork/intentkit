from __future__ import annotations

import logging
from decimal import Decimal

from epyxid import XID
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.core.agent import get_agent
from intentkit.models.agent_data import AgentData
from intentkit.models.credit import (
    DEFAULT_PLATFORM_ACCOUNT_WITHDRAW,
    CreditAccount,
    CreditDebit,
    CreditEvent,
    CreditEventTable,
    CreditTransactionTable,
    CreditType,
    Direction,
    EventType,
    OwnerType,
    TransactionType,
    UpstreamType,
)
from intentkit.utils.alert import send_alert
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


async def withdraw(
    session: AsyncSession,
    agent_id: str,
    amount: Decimal,
    upstream_tx_id: str,
    note: str | None = None,
) -> CreditAccount:
    """
    Withdraw credits from an agent account to platform account.

    Args:
        session: Async session to use for database operations
        agent_id: ID of the agent to withdraw from
        amount: Amount of credits to withdraw
        upstream_tx_id: ID of the upstream transaction
        note: Optional note for the transaction

    Returns:
        Updated agent credit account
    """
    # Check for idempotency - prevent duplicate transactions
    await CreditEvent.check_upstream_tx_id_exists(
        session, UpstreamType.API, upstream_tx_id
    )

    if amount <= Decimal("0"):
        raise ValueError("Withdraw amount must be positive")

    # Get agent to retrieve user_id from agent.owner
    agent = await get_agent(agent_id)
    if not agent:
        raise IntentKitAPIError(
            status_code=404, key="AgentNotFound", message="Agent not found"
        )

    if not agent.owner:
        raise IntentKitAPIError(
            status_code=400, key="AgentNoOwner", message="Agent has no owner"
        )

    # Get agent wallet address
    agent_data = await AgentData.get(agent.id)
    agent_wallet_address = agent_data.evm_wallet_address if agent_data else None

    user_id = agent.owner

    # Get agent account to check balance
    agent_account = await CreditAccount.get_in_session(
        session=session,
        owner_type=OwnerType.AGENT,
        owner_id=agent_id,
    )

    # Check if agent has sufficient permanent credits
    if agent_account.credits < amount:
        raise IntentKitAPIError(
            status_code=400,
            key="InsufficientBalance",
            message=f"Insufficient balance. Available: {agent_account.credits}, Required: {amount}",
        )

    # 1. Create credit event record first to get event_id
    event_id = str(XID())

    # 2. Update agent account - deduct credits
    updated_agent_account = await CreditAccount.deduction_in_session(
        session=session,
        owner_type=OwnerType.AGENT,
        owner_id=agent_id,
        credit_type=CreditType.PERMANENT,
        amount=amount,
        event_id=event_id,
    )

    # 3. Update platform withdraw account - add credits
    platform_account = await CreditAccount.income_in_session(
        session=session,
        owner_type=OwnerType.PLATFORM,
        owner_id=DEFAULT_PLATFORM_ACCOUNT_WITHDRAW,
        amount_details={
            CreditType.PERMANENT: amount
        },  # Withdraw adds to platform permanent credits
        event_id=event_id,
    )

    # 4. Create credit event record
    event = CreditEventTable(
        id=event_id,
        event_type=EventType.WITHDRAW,
        user_id=user_id,
        upstream_type=UpstreamType.API,
        upstream_tx_id=upstream_tx_id,
        direction=Direction.EXPENSE,
        account_id=updated_agent_account.id,
        total_amount=amount,
        credit_type=CreditType.PERMANENT,
        credit_types=[CreditType.PERMANENT],
        balance_after=updated_agent_account.credits
        + updated_agent_account.free_credits
        + updated_agent_account.reward_credits,
        base_amount=amount,
        base_original_amount=amount,
        base_free_amount=Decimal("0"),  # No free credits involved in base amount
        base_reward_amount=Decimal("0"),  # No reward credits involved in base amount
        base_permanent_amount=amount,  # All base amount is permanent for withdraw
        permanent_amount=amount,  # Set permanent_amount since this is a permanent credit
        free_amount=Decimal("0"),  # No free credits involved
        reward_amount=Decimal("0"),  # No reward credits involved
        agent_wallet_address=agent_wallet_address,  # Include agent wallet address
        note=note,
    )
    session.add(event)
    await session.flush()

    # 5. Create credit transaction records
    # 5.1 Agent account transaction (debit)
    agent_tx = CreditTransactionTable(
        id=str(XID()),
        account_id=updated_agent_account.id,
        event_id=event_id,
        tx_type=TransactionType.WITHDRAW,
        credit_debit=CreditDebit.DEBIT,
        change_amount=amount,
        credit_type=CreditType.PERMANENT,
        free_amount=Decimal("0"),
        reward_amount=Decimal("0"),
        permanent_amount=amount,
    )
    session.add(agent_tx)

    # 5.2 Platform withdraw account transaction (credit)
    platform_tx = CreditTransactionTable(
        id=str(XID()),
        account_id=platform_account.id,
        event_id=event_id,
        tx_type=TransactionType.WITHDRAW,
        credit_debit=CreditDebit.CREDIT,
        change_amount=amount,
        credit_type=CreditType.PERMANENT,
        free_amount=Decimal("0"),
        reward_amount=Decimal("0"),
        permanent_amount=amount,
    )
    session.add(platform_tx)

    # Commit all changes
    await session.commit()

    # Send notification for withdraw
    try:
        send_alert(
            f"💸 **Credit Withdraw**\n"
            f"• Agent ID: `{agent_id}`\n"
            f"• User ID: `{user_id}`\n"
            f"• Amount: `{amount}` credits\n"
            f"• Transaction ID: `{upstream_tx_id}`\n"
            f"• New Balance: `{updated_agent_account.credits}` credits\n"
            f"• Note: {note or 'N/A'}"
        )
    except Exception as e:
        logger.error(f"Failed to send notification for withdraw: {str(e)}")

    return updated_agent_account
