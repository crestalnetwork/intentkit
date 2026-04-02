"""Tests for intentkit.core.credit.plan_credit."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.core.credit.plan_credit import (
    issue_all_plan_credits,
    issue_plan_credits_for_team,
)
from intentkit.models.credit import (
    CreditType,
    EventType,
    OwnerType,
    TransactionType,
)
from intentkit.models.team import TeamPlan


@pytest.mark.asyncio
async def test_issue_plan_credits_for_team_creates_records():
    """Verify income, deduction, event, and transactions are created."""
    mock_team_account = MagicMock()
    mock_team_account.id = "acc-team"
    mock_team_account.credits = Decimal("100")
    mock_team_account.free_credits = Decimal("50")
    mock_team_account.reward_credits = Decimal("0")

    mock_platform_account = MagicMock()
    mock_platform_account.id = "platform_plan_credit"

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    with (
        patch(
            "intentkit.core.credit.plan_credit.CreditAccount.income_in_session",
            new_callable=AsyncMock,
            return_value=mock_team_account,
        ) as mock_income,
        patch(
            "intentkit.core.credit.plan_credit.CreditAccount.deduction_in_session",
            new_callable=AsyncMock,
            return_value=mock_platform_account,
        ) as mock_deduction,
    ):
        await issue_plan_credits_for_team(mock_session, "team-1", Decimal("10000"))

    mock_income.assert_called_once()
    assert mock_income.call_args[1]["amount_details"] == {
        CreditType.PERMANENT: Decimal("10000")
    }
    assert mock_income.call_args[1]["owner_type"] == OwnerType.TEAM

    mock_deduction.assert_called_once()
    assert mock_deduction.call_args[1]["credit_type"] == CreditType.PERMANENT
    assert mock_deduction.call_args[1]["amount"] == Decimal("10000")

    # event + 2 transactions = 3 add() calls
    assert mock_session.add.call_count == 3
    added = [call.args[0] for call in mock_session.add.call_args_list]

    event = next(obj for obj in added if hasattr(obj, "event_type"))
    assert event.event_type == EventType.PLAN_CREDIT
    assert event.total_amount == Decimal("10000")

    txs = [obj for obj in added if hasattr(obj, "tx_type")]
    assert len(txs) == 2
    tx_types = {tx.tx_type for tx in txs}
    assert tx_types == {TransactionType.PLAN_CREDIT}

    # Should NOT commit — caller controls the transaction
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_issue_all_skips_team_not_due():
    """Team with next_credit_issue_at far in the future is not selected."""
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = None
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "intentkit.core.credit.plan_credit.get_session",
            return_value=ctx,
        ),
        patch(
            "intentkit.core.credit.plan_credit.issue_plan_credits_for_team",
            new_callable=AsyncMock,
        ) as mock_issue,
    ):
        await issue_all_plan_credits()

    mock_issue.assert_not_called()


@pytest.mark.asyncio
async def test_issue_all_uses_2hour_window_and_original_schedule():
    """Credits are issued when next_credit_issue_at is within 2h,
    and next schedule is based on original time, not now."""
    # Team scheduled 1 hour from now — within the 2h window
    now = datetime(2026, 4, 15, 10, 0, 0, tzinfo=UTC)
    scheduled_at = datetime(2026, 4, 15, 11, 0, 0, tzinfo=UTC)

    mock_team = MagicMock()
    mock_team.id = "team-pro"
    mock_team.plan = TeamPlan.PRO.value
    mock_team.next_credit_issue_at = scheduled_at
    mock_team.plan_expires_at = None

    # First call returns team, second returns None to break the loop
    call_count = 0

    def make_scalars_result():
        nonlocal call_count
        call_count += 1
        mock_scalars = MagicMock()
        if call_count == 1:
            mock_scalars.first.return_value = mock_team
        else:
            mock_scalars.first.return_value = None
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        return mock_result

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=lambda stmt: make_scalars_result())
    mock_session.add = MagicMock()

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "intentkit.core.credit.plan_credit.get_session",
            return_value=ctx,
        ),
        patch(
            "intentkit.core.credit.plan_credit.datetime",
        ) as mock_datetime,
        patch(
            "intentkit.core.credit.plan_credit.issue_plan_credits_for_team",
            new_callable=AsyncMock,
        ) as mock_issue,
        patch(
            "intentkit.core.credit.plan_credit.add_month",
            return_value=datetime(2026, 5, 15, 11, 0, 0, tzinfo=UTC),
        ) as mock_add_month,
    ):
        mock_datetime.now.return_value = now
        mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)
        await issue_all_plan_credits()

    mock_issue.assert_called_once_with(mock_session, "team-pro", Decimal("10000"))
    # add_month should be called with the original scheduled_at, not now
    mock_add_month.assert_called_once_with(scheduled_at)
    mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_issue_all_does_not_issue_beyond_2hour_window():
    """Team with next_credit_issue_at >2h away should not be picked up."""
    now = datetime(2026, 4, 15, 10, 0, 0, tzinfo=UTC)

    # No team returned because the query filters by cutoff = now + 2h
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = None
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "intentkit.core.credit.plan_credit.get_session",
            return_value=ctx,
        ),
        patch(
            "intentkit.core.credit.plan_credit.datetime",
        ) as mock_datetime,
        patch(
            "intentkit.core.credit.plan_credit.issue_plan_credits_for_team",
            new_callable=AsyncMock,
        ) as mock_issue,
    ):
        mock_datetime.now.return_value = now
        mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)
        await issue_all_plan_credits()

    mock_issue.assert_not_called()


@pytest.mark.asyncio
async def test_issue_all_rollback_on_error():
    """On error, transaction is rolled back and loop continues."""
    now = datetime(2026, 4, 15, 10, 0, 0, tzinfo=UTC)
    scheduled_at = datetime(2026, 4, 15, 9, 0, 0, tzinfo=UTC)

    mock_team = MagicMock()
    mock_team.id = "team-err"
    mock_team.plan = TeamPlan.PRO.value
    mock_team.next_credit_issue_at = scheduled_at
    mock_team.plan_expires_at = None

    call_count = 0

    def make_scalars_result():
        nonlocal call_count
        call_count += 1
        mock_scalars = MagicMock()
        if call_count == 1:
            mock_scalars.first.return_value = mock_team
        else:
            mock_scalars.first.return_value = None
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        return mock_result

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=lambda stmt: make_scalars_result())

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "intentkit.core.credit.plan_credit.get_session",
            return_value=ctx,
        ),
        patch(
            "intentkit.core.credit.plan_credit.datetime",
        ) as mock_datetime,
        patch(
            "intentkit.core.credit.plan_credit.issue_plan_credits_for_team",
            new_callable=AsyncMock,
            side_effect=Exception("DB error"),
        ),
    ):
        mock_datetime.now.return_value = now
        mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)
        await issue_all_plan_credits()

    mock_session.rollback.assert_called_once()
    mock_session.commit.assert_not_called()
