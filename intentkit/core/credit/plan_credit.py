"""Monthly plan credit issuance for teams."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from epyxid import XID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.db import get_session
from intentkit.models.credit import (
    DEFAULT_PLATFORM_ACCOUNT_PLAN_CREDIT,
    CreditAccount,
    CreditDebit,
    CreditEventTable,
    CreditTransactionTable,
    CreditType,
    Direction,
    EventType,
    OwnerType,
    TransactionType,
    UpstreamType,
)
from intentkit.models.team import PLAN_CONFIGS, TeamPlan, TeamTable
from intentkit.utils.time import add_month

logger = logging.getLogger(__name__)


async def issue_plan_credits_for_team(
    session: AsyncSession,
    team_id: str,
    amount: Decimal,
) -> None:
    """Issue monthly permanent credits to a single team.

    Args:
        session: Async session to use for database operations
        team_id: ID of the team
        amount: Amount of permanent credits to issue
    """
    event_id = str(XID())

    team_account = await CreditAccount.income_in_session(
        session=session,
        owner_type=OwnerType.TEAM,
        owner_id=team_id,
        amount_details={CreditType.PERMANENT: amount},
        event_id=event_id,
    )

    platform_account = await CreditAccount.deduction_in_session(
        session=session,
        owner_type=OwnerType.PLATFORM,
        owner_id=DEFAULT_PLATFORM_ACCOUNT_PLAN_CREDIT,
        credit_type=CreditType.PERMANENT,
        amount=amount,
        event_id=event_id,
    )

    event = CreditEventTable(
        id=event_id,
        event_type=EventType.PLAN_CREDIT,
        team_id=team_id,
        upstream_type=UpstreamType.SCHEDULER,
        upstream_tx_id=str(XID()),
        direction=Direction.INCOME,
        account_id=team_account.id,
        credit_type=CreditType.PERMANENT,
        credit_types=[CreditType.PERMANENT],
        total_amount=amount,
        balance_after=team_account.credits
        + team_account.free_credits
        + team_account.reward_credits,
        base_amount=amount,
        base_original_amount=amount,
        base_free_amount=Decimal("0"),
        base_reward_amount=Decimal("0"),
        base_permanent_amount=amount,
        permanent_amount=amount,
        free_amount=Decimal("0"),
        reward_amount=Decimal("0"),
        agent_wallet_address=None,
        note="Monthly plan credit issue",
    )
    session.add(event)
    await session.flush()

    team_tx = CreditTransactionTable(
        id=str(XID()),
        account_id=team_account.id,
        event_id=event_id,
        tx_type=TransactionType.PLAN_CREDIT,
        credit_debit=CreditDebit.CREDIT,
        change_amount=amount,
        credit_type=CreditType.PERMANENT,
        free_amount=Decimal("0"),
        reward_amount=Decimal("0"),
        permanent_amount=amount,
    )
    session.add(team_tx)

    platform_tx = CreditTransactionTable(
        id=str(XID()),
        account_id=platform_account.id,
        event_id=event_id,
        tx_type=TransactionType.PLAN_CREDIT,
        credit_debit=CreditDebit.DEBIT,
        change_amount=amount,
        credit_type=CreditType.PERMANENT,
        free_amount=Decimal("0"),
        reward_amount=Decimal("0"),
        permanent_amount=amount,
    )
    session.add(platform_tx)

    logger.info("Issued %s plan credits to team %s", amount, team_id)


async def issue_all_plan_credits() -> None:
    """Find all teams due for monthly credit issuance and process them.

    Uses FOR UPDATE SKIP LOCKED to prevent duplicate payouts from
    concurrent scheduler runs.
    """
    now = datetime.now(UTC)
    # Issue credits if scheduled time is within 2 hours from now
    cutoff = now + timedelta(hours=2)

    issued_count = 0
    while True:
        async with get_session() as session:
            stmt = (
                select(TeamTable)
                .where(
                    TeamTable.plan.in_([TeamPlan.PRO.value, TeamPlan.MAX.value]),
                    TeamTable.next_credit_issue_at <= cutoff,
                    (TeamTable.plan_expires_at.is_(None))
                    | (TeamTable.plan_expires_at > now),
                )
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            result = await session.execute(stmt)
            team = result.scalars().first()
            if team is None:
                break

            plan_value = team.plan
            if plan_value.startswith("TeamPlan."):
                plan_value = plan_value.removeprefix("TeamPlan.").lower()
            plan = TeamPlan(plan_value)
            plan_config = PLAN_CONFIGS[plan]
            # Base next issue on the originally scheduled time, not actual run time
            scheduled_at = team.next_credit_issue_at or now
            next_issue = add_month(scheduled_at)

            if plan_config.monthly_permanent_credits <= 0:
                stmt_update = (
                    update(TeamTable)
                    .where(TeamTable.id == team.id)
                    .values(next_credit_issue_at=next_issue)
                )
                await session.execute(stmt_update)
                await session.commit()
                continue

            try:
                await issue_plan_credits_for_team(
                    session, team.id, plan_config.monthly_permanent_credits
                )
                stmt_update = (
                    update(TeamTable)
                    .where(TeamTable.id == team.id)
                    .values(next_credit_issue_at=next_issue)
                )
                await session.execute(stmt_update)
                await session.commit()
                issued_count += 1
            except Exception as e:
                logger.error("Error issuing plan credits for team %s: %s", team.id, e)
                await session.rollback()

    logger.info("Issued monthly plan credits to %s teams", issued_count)
