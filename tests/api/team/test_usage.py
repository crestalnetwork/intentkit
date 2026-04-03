"""Tests for team usage endpoint."""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.models.credit import CreditAccount, OwnerType
from intentkit.utils.error import IntentKitAPIError


def _make_account() -> CreditAccount:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    return CreditAccount(
        id="acc-1",
        owner_type=OwnerType.TEAM,
        owner_id="team-1",
        free_quota=Decimal("50"),
        refill_amount=Decimal("1"),
        free_credits=Decimal("30"),
        reward_credits=Decimal("10"),
        credits=Decimal("100"),
        income_at=now,
        expense_at=now,
        last_event_id="evt-1",
        total_income=Decimal("200"),
        total_free_income=Decimal("50"),
        total_reward_income=Decimal("10"),
        total_permanent_income=Decimal("140"),
        total_expense=Decimal("60"),
        total_free_expense=Decimal("20"),
        total_reward_expense=Decimal("0"),
        total_permanent_expense=Decimal("40"),
        created_at=now,
        updated_at=now,
    )


class TestGetTeamUsage:
    @pytest.mark.asyncio
    async def test_returns_account_and_events(self):
        from app.team.usage import get_team_usage

        account = _make_account()

        with (
            patch(
                "app.team.usage.get_session",
            ) as mock_get_session,
            patch(
                "app.team.usage.CreditAccount.get_in_session",
                new_callable=AsyncMock,
                return_value=account,
            ),
            patch(
                "app.team.usage.list_credit_events_by_team",
                new_callable=AsyncMock,
                return_value=([], None, False),
            ),
        ):
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_get_session.return_value = mock_session

            response = await get_team_usage(
                direction=None,
                event_type=None,
                cursor=None,
                limit=50,
                auth=("user-1", "team-1"),
            )

        data = json.loads(bytes(response.body).decode("utf-8"))
        assert data["account"]["id"] == "acc-1"
        assert data["account"]["free_credits"] == "30.0000"
        assert data["account"]["free_quota"] == "50.0000"
        assert data["events"] == []
        assert data["next_cursor"] is None
        assert data["has_more"] is False

    @pytest.mark.asyncio
    async def test_returns_null_account_when_not_found(self):
        from app.team.usage import get_team_usage

        with (
            patch("app.team.usage.get_session") as mock_get_session,
            patch(
                "app.team.usage.CreditAccount.get_in_session",
                new_callable=AsyncMock,
                side_effect=IntentKitAPIError(
                    status_code=404,
                    key="CreditAccountNotFound",
                    message="Credit account not found",
                ),
            ),
            patch(
                "app.team.usage.list_credit_events_by_team",
                new_callable=AsyncMock,
                return_value=([], None, False),
            ),
        ):
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_get_session.return_value = mock_session

            response = await get_team_usage(
                direction=None,
                event_type=None,
                cursor=None,
                limit=50,
                auth=("user-1", "team-1"),
            )

        data = json.loads(bytes(response.body).decode("utf-8"))
        assert data["account"] is None
        assert data["events"] == []
