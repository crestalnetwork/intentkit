from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.core.credit import (
    fetch_credit_event_by_id,
    fetch_credit_event_by_upstream_tx_id,
    list_credit_events,
    list_credit_events_by_user,
    list_fee_events_by_agent,
)
from intentkit.models.credit import (
    CreditEventTable,
    Direction,
    EventType,
    OwnerType,
)
from intentkit.utils.error import IntentKitAPIError


class SelectQueryStub:
    def __init__(self, items: list[CreditEventTable]):
        self.items = items
        self.conditions: list[tuple[str, str, object]] = []
        self.limit_value: int | None = None
        self.orderings: list[str] = []

    def where(self, condition: object):
        left = getattr(condition, "left", None)
        right = getattr(condition, "right", None)
        operator = getattr(condition, "operator", None)
        key = getattr(left, "key", "")
        op = getattr(operator, "__name__", str(operator))
        self.conditions.append((key, op, right.value if hasattr(right, "value") else right))
        return self

    def order_by(self, *_args):
        self.orderings.append("order")
        return self

    def limit(self, limit: int):
        self.limit_value = limit
        return self


@pytest.mark.asyncio
async def test_list_credit_events_by_user_filters_and_pagination():
    account = MagicMock()
    account.id = "acc-1"

    events = [
        CreditEventTable(
            id="event-3",
            account_id="acc-1",
            event_type=EventType.RECHARGE.value,
            user_id="user-1",
            upstream_type="api",
            upstream_tx_id="tx-3",
            direction=Direction.INCOME.value,
            total_amount=Decimal("1.0"),
            credit_type="credits",
        ),
        CreditEventTable(
            id="event-2",
            account_id="acc-1",
            event_type=EventType.RECHARGE.value,
            user_id="user-1",
            upstream_type="api",
            upstream_tx_id="tx-2",
            direction=Direction.INCOME.value,
            total_amount=Decimal("1.0"),
            credit_type="credits",
        ),
    ]

    fake_select = SelectQueryStub(events)

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = events
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    with (
        patch(
            "intentkit.core.credit.list_events.CreditAccount.get_in_session",
            new_callable=AsyncMock,
            return_value=account,
        ),
        patch("intentkit.core.credit.list_events.select", return_value=fake_select),
        patch(
            "intentkit.core.credit.list_events.CreditEvent.model_validate",
            side_effect=lambda event: event,
        ),
    ):
        result, cursor, has_more = await list_credit_events_by_user(
            mock_session,
            "user-1",
            direction=Direction.INCOME,
            cursor="event-4",
            limit=1,
            event_type=EventType.RECHARGE,
        )

    assert result == [events[0]]
    assert cursor == "event-3"
    assert has_more is True
    condition_keys = {cond[0] for cond in fake_select.conditions}
    assert {"account_id", "direction", "event_type", "id"} <= condition_keys


@pytest.mark.asyncio
async def test_list_credit_events_by_user_missing_account():
    mock_session = AsyncMock()

    with patch(
        "intentkit.core.credit.list_events.CreditAccount.get_in_session",
        new_callable=AsyncMock,
        return_value=None,
    ):
        events, cursor, has_more = await list_credit_events_by_user(
            mock_session, "missing"
        )

    assert events == []
    assert cursor is None
    assert has_more is False


@pytest.mark.asyncio
async def test_list_credit_events_with_time_range_and_cursor():
    start_at = datetime.now(UTC) - timedelta(days=1)
    end_at = datetime.now(UTC)
    events = [
        CreditEventTable(
            id="event-1",
            account_id="acc-1",
            event_type=EventType.MESSAGE.value,
            user_id="user-1",
            upstream_type="executor",
            upstream_tx_id="tx-1",
            direction=Direction.EXPENSE.value,
            total_amount=Decimal("1.0"),
            credit_type="credits",
        )
    ]

    fake_select = SelectQueryStub(events)

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = events
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    with (
        patch("intentkit.core.credit.list_events.select", return_value=fake_select),
        patch(
            "intentkit.core.credit.list_events.CreditEvent.model_validate",
            side_effect=lambda event: event,
        ),
    ):
        result, cursor, has_more = await list_credit_events(
            mock_session,
            direction=Direction.EXPENSE,
            cursor="event-0",
            limit=10,
            event_type=EventType.MESSAGE,
            start_at=start_at,
            end_at=end_at,
        )

    assert result == events
    assert cursor == "event-1"
    assert has_more is False
    condition_keys = {cond[0] for cond in fake_select.conditions}
    assert {"direction", "event_type", "created_at", "id"} <= condition_keys


@pytest.mark.asyncio
async def test_list_fee_events_by_agent_with_cursor():
    agent_account = MagicMock()
    agent_account.id = "agent-acc"

    events = [
        CreditEventTable(
            id="event-2",
            account_id="acc-user",
            event_type=EventType.MESSAGE.value,
            user_id="user-1",
            upstream_type="executor",
            upstream_tx_id="tx-2",
            direction=Direction.EXPENSE.value,
            total_amount=Decimal("1.0"),
            credit_type="credits",
            fee_agent_account="agent-acc",
            fee_agent_amount=Decimal("0.1"),
        )
    ]

    fake_select = SelectQueryStub(events)
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = events
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    with (
        patch(
            "intentkit.core.credit.list_events.CreditAccount.get_in_session",
            new_callable=AsyncMock,
            return_value=agent_account,
        ),
        patch("intentkit.core.credit.list_events.select", return_value=fake_select),
        patch(
            "intentkit.core.credit.list_events.CreditEvent.model_validate",
            side_effect=lambda event: event,
        ),
    ):
        result, cursor, has_more = await list_fee_events_by_agent(
            mock_session, "agent-1", cursor="event-3", limit=1
        )

    assert result == events
    assert cursor is None
    assert has_more is False
    condition_keys = {cond[0] for cond in fake_select.conditions}
    assert {"fee_agent_account", "fee_agent_amount", "id"} <= condition_keys


@pytest.mark.asyncio
async def test_list_fee_events_by_agent_missing_account():
    mock_session = AsyncMock()

    with patch(
        "intentkit.core.credit.list_events.CreditAccount.get_in_session",
        new_callable=AsyncMock,
        return_value=None,
    ):
        events, cursor, has_more = await list_fee_events_by_agent(mock_session, "agent")

    assert events == []
    assert cursor is None
    assert has_more is False


@pytest.mark.asyncio
async def test_fetch_credit_event_by_upstream_tx_id_success():
    event = CreditEventTable(
        id="event-1",
        account_id="acc-1",
        event_type=EventType.MESSAGE.value,
        user_id="user-1",
        upstream_type="executor",
        upstream_tx_id="tx-1",
        direction=Direction.EXPENSE.value,
        total_amount=Decimal("1.0"),
        credit_type="credits",
    )

    mock_session = AsyncMock()
    mock_session.scalar.return_value = event

    with patch(
        "intentkit.core.credit.list_events.CreditEvent.model_validate",
        side_effect=lambda model: model,
    ):
        result = await fetch_credit_event_by_upstream_tx_id(mock_session, "tx-1")

    assert result == event


@pytest.mark.asyncio
async def test_fetch_credit_event_by_upstream_tx_id_missing():
    mock_session = AsyncMock()
    mock_session.scalar.return_value = None

    with pytest.raises(IntentKitAPIError) as excinfo:
        await fetch_credit_event_by_upstream_tx_id(mock_session, "missing")

    assert "Credit event with upstream_tx_id" in str(excinfo.value)


@pytest.mark.asyncio
async def test_fetch_credit_event_by_id_success():
    event = CreditEventTable(
        id="event-1",
        account_id="acc-1",
        event_type=EventType.MESSAGE.value,
        user_id="user-1",
        upstream_type="executor",
        upstream_tx_id="tx-1",
        direction=Direction.EXPENSE.value,
        total_amount=Decimal("1.0"),
        credit_type="credits",
    )

    mock_session = AsyncMock()
    mock_session.scalar.return_value = event

    with patch(
        "intentkit.core.credit.list_events.CreditEvent.model_validate",
        side_effect=lambda model: model,
    ):
        result = await fetch_credit_event_by_id(mock_session, "event-1")

    assert result == event


@pytest.mark.asyncio
async def test_fetch_credit_event_by_id_missing():
    mock_session = AsyncMock()
    mock_session.scalar.return_value = None

    with pytest.raises(IntentKitAPIError) as excinfo:
        await fetch_credit_event_by_id(mock_session, "missing")

    assert "Credit event with ID" in str(excinfo.value)
