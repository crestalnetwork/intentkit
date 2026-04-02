from __future__ import annotations

import logging
from decimal import Decimal

from epyxid import XID
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.models.credit import (
    DEFAULT_PLATFORM_ACCOUNT_REWARD,
    CreditAccount,
    CreditDebit,
    CreditEvent,
    CreditEventTable,
    CreditTransactionTable,
    CreditType,
    Direction,
    OwnerType,
    RewardType,
    UpstreamType,
)
from intentkit.utils.alert import send_alert

logger = logging.getLogger(__name__)


async def reward(
    session: AsyncSession,
    team_id: str,
    amount: Decimal,
    upstream_tx_id: str,
    note: str | None = None,
    reward_type: RewardType | None = RewardType.REWARD,
) -> CreditAccount:
    """
    Reward a team account with reward credits.

    Args:
        session: Async session to use for database operations
        team_id: ID of the team to reward
        amount: Amount of reward credits to add
        upstream_tx_id: ID of the upstream transaction
        note: Optional note for the transaction

    Returns:
        Updated team credit account
    """
    # Check for idempotency - prevent duplicate transactions
    await CreditEvent.check_upstream_tx_id_exists(
        session, UpstreamType.API, upstream_tx_id
    )

    if amount <= Decimal("0"):
        raise ValueError("Reward amount must be positive")

    # 1. Create credit event record first to get event_id
    event_id = str(XID())

    # 2. Update team account - add reward credits
    team_account = await CreditAccount.income_in_session(
        session=session,
        owner_type=OwnerType.TEAM,
        owner_id=team_id,
        amount_details={CreditType.REWARD: amount},  # Reward adds to reward credits
        event_id=event_id,
    )

    # 3. Update platform reward account - deduct credits
    platform_account = await CreditAccount.deduction_in_session(
        session=session,
        owner_type=OwnerType.PLATFORM,
        owner_id=DEFAULT_PLATFORM_ACCOUNT_REWARD,
        credit_type=CreditType.REWARD,
        amount=amount,
        event_id=event_id,
    )

    # 4. Create credit event record
    event = CreditEventTable(
        id=event_id,
        event_type=reward_type,
        team_id=team_id,
        upstream_type=UpstreamType.API,
        upstream_tx_id=upstream_tx_id,
        direction=Direction.INCOME,
        account_id=team_account.id,
        total_amount=amount,
        credit_type=CreditType.REWARD,
        credit_types=[CreditType.REWARD],
        balance_after=team_account.credits
        + team_account.free_credits
        + team_account.reward_credits,
        base_amount=amount,
        base_original_amount=amount,
        base_free_amount=Decimal("0"),  # No free credits involved in base amount
        base_reward_amount=amount,  # All base amount is reward for reward events
        base_permanent_amount=Decimal(
            "0"
        ),  # No permanent credits involved in base amount
        reward_amount=amount,  # Set reward_amount since this is a reward credit
        free_amount=Decimal("0"),  # No free credits involved
        permanent_amount=Decimal("0"),  # No permanent credits involved
        agent_wallet_address=None,  # No agent involved in reward
        note=note,
    )
    session.add(event)
    await session.flush()

    # 4. Create credit transaction records
    # 4.1 Team account transaction (credit)
    team_tx = CreditTransactionTable(
        id=str(XID()),
        account_id=team_account.id,
        event_id=event_id,
        tx_type=reward_type,
        credit_debit=CreditDebit.CREDIT,
        change_amount=amount,
        credit_type=CreditType.REWARD,
        free_amount=Decimal("0"),
        reward_amount=amount,
        permanent_amount=Decimal("0"),
    )
    session.add(team_tx)

    # 4.2 Platform reward account transaction (debit)
    platform_tx = CreditTransactionTable(
        id=str(XID()),
        account_id=platform_account.id,
        event_id=event_id,
        tx_type=reward_type,
        credit_debit=CreditDebit.DEBIT,
        change_amount=amount,
        credit_type=CreditType.REWARD,
        free_amount=Decimal("0"),
        reward_amount=amount,
        permanent_amount=Decimal("0"),
    )
    session.add(platform_tx)

    # Commit all changes
    await session.commit()

    # Send notification for reward
    try:
        reward_type_name = reward_type.value if reward_type else "REWARD"
        send_alert(
            f"🎁 **Credit Reward**\n"
            f"• Team ID: `{team_id}`\n"
            f"• Amount: `{amount}` reward credits\n"
            f"• Transaction ID: `{upstream_tx_id}`\n"
            f"• Reward Type: `{reward_type_name}`\n"
            f"• New Balance: `{team_account.credits + team_account.free_credits + team_account.reward_credits}` credits\n"
            f"• Note: {note or 'N/A'}"
        )
    except Exception as e:
        logger.error("Failed to send notification for reward: %s", e)

    return team_account
