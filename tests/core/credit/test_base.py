from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.core.credit import update_credit_event_note, update_daily_quota
from intentkit.models.credit import CreditAccountTable, CreditEventTable
from intentkit.utils.error import IntentKitAPIError


@pytest.mark.asyncio
async def test_update_credit_event_note_success():
    mock_event = MagicMock(spec=CreditEventTable)
    mock_event.id = "event-1"
    mock_event.note = None

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_event

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    with patch(
        "intentkit.models.credit.CreditEvent.model_validate", return_value=mock_event
    ) as mock_validate:
        result = await update_credit_event_note(mock_session, "event-1", "updated")

    assert result == mock_event
    assert mock_event.note == "updated"
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once_with(mock_event)
    mock_validate.assert_called_once_with(mock_event)


@pytest.mark.asyncio
async def test_update_credit_event_note_missing_event():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    with pytest.raises(IntentKitAPIError) as excinfo:
        await update_credit_event_note(mock_session, "missing")

    assert "CreditEventNotFound" in str(excinfo.value)


@pytest.mark.asyncio
async def test_update_daily_quota_delegates_to_model():
    mock_session = AsyncMock()
    mock_account = MagicMock(spec=CreditAccountTable)

    with patch(
        "intentkit.models.credit.CreditAccount.update_daily_quota",
        new_callable=AsyncMock,
    ) as mock_update:
        mock_update.return_value = mock_account
        result = await update_daily_quota(
            mock_session,
            "user-1",
            free_quota=Decimal("2.5"),
            refill_amount=Decimal("1.0"),
            upstream_tx_id="tx-1",
            note="adjust",
        )

    assert result == mock_account
    mock_update.assert_called_once_with(
        mock_session, "user-1", Decimal("2.5"), Decimal("1.0"), "tx-1", "adjust"
    )
