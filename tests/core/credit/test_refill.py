from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.core.credit.refill import (
    refill_all_free_credits,
    refill_free_credits_for_account,
)
from intentkit.models.credit import CreditAccount, CreditAccountTable, CreditType, OwnerType


@pytest.mark.asyncio
async def test_refill_free_credits_for_account_skips_zero_refill():
    account = CreditAccount(
        id="acc-1",
        owner_type=OwnerType.USER,
        owner_id="user-1",
        free_quota=Decimal("10.0000"),
        refill_amount=Decimal("0"),
        free_credits=Decimal("5.0000"),
        reward_credits=Decimal("0"),
        credits=Decimal("0"),
        income_at=None,
        expense_at=None,
        last_event_id=None,
        total_income=Decimal("0"),
        total_free_income=Decimal("0"),
        total_reward_income=Decimal("0"),
        total_permanent_income=Decimal("0"),
        total_expense=Decimal("0"),
        total_free_expense=Decimal("0"),
        total_reward_expense=Decimal("0"),
        total_permanent_expense=Decimal("0"),
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )

    mock_session = AsyncMock()

    with patch(
        "intentkit.models.credit.CreditAccount.income_in_session", new_callable=AsyncMock
    ) as mock_income:
        await refill_free_credits_for_account(mock_session, account)

    mock_income.assert_not_called()


@pytest.mark.asyncio
async def test_refill_free_credits_for_account_adds_amount():
    account = CreditAccount(
        id="acc-1",
        owner_type=OwnerType.USER,
        owner_id="user-1",
        free_quota=Decimal("10.0000"),
        refill_amount=Decimal("3.0000"),
        free_credits=Decimal("8.0000"),
        reward_credits=Decimal("0"),
        credits=Decimal("0"),
        income_at=None,
        expense_at=None,
        last_event_id=None,
        total_income=Decimal("0"),
        total_free_income=Decimal("0"),
        total_reward_income=Decimal("0"),
        total_permanent_income=Decimal("0"),
        total_expense=Decimal("0"),
        total_free_expense=Decimal("0"),
        total_reward_expense=Decimal("0"),
        total_permanent_expense=Decimal("0"),
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )

    updated_account = MagicMock(spec=CreditAccountTable)
    updated_account.id = "acc-1"
    updated_account.credits = Decimal("0")
    updated_account.free_credits = Decimal("10.0000")
    updated_account.reward_credits = Decimal("0")

    platform_account = MagicMock(spec=CreditAccountTable)
    platform_account.id = "platform_refill"

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    with (
        patch(
            "intentkit.models.credit.CreditAccount.income_in_session",
            new_callable=AsyncMock,
            return_value=updated_account,
        ) as mock_income,
        patch(
            "intentkit.models.credit.CreditAccount.deduction_in_session",
            new_callable=AsyncMock,
            return_value=platform_account,
        ) as mock_deduction,
    ):
        await refill_free_credits_for_account(mock_session, account)

    mock_income.assert_called_once()
    # Free quota (10.0000) minus current free credits (8.0000) limits the refill to 2.0000.
    assert mock_income.call_args[1]["amount_details"] == {
        CreditType.FREE: Decimal("2.0000")
    }
    mock_deduction.assert_called_once()
    mock_session.commit.assert_called_once()

    added_objects = [call.args[0] for call in mock_session.add.call_args_list]
    event = next(obj for obj in added_objects if hasattr(obj, "event_type"))
    assert event.total_amount == Decimal("2.0000")


@pytest.mark.asyncio
async def test_refill_all_free_credits_iterates_accounts():
    account = CreditAccount(
        id="acc-1",
        owner_type=OwnerType.USER,
        owner_id="user-1",
        free_quota=Decimal("10.0000"),
        refill_amount=Decimal("1.0000"),
        free_credits=Decimal("5.0000"),
        reward_credits=Decimal("0"),
        credits=Decimal("0"),
        income_at=None,
        expense_at=None,
        last_event_id=None,
        total_income=Decimal("0"),
        total_free_income=Decimal("0"),
        total_reward_income=Decimal("0"),
        total_permanent_income=Decimal("0"),
        total_expense=Decimal("0"),
        total_free_expense=Decimal("0"),
        total_reward_expense=Decimal("0"),
        total_permanent_expense=Decimal("0"),
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [MagicMock()]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    first_session = AsyncMock()
    first_session.execute.return_value = mock_result

    second_session = AsyncMock()

    first_ctx = MagicMock()
    first_ctx.__aenter__.return_value = first_session
    first_ctx.__aexit__.return_value = None

    second_ctx = MagicMock()
    second_ctx.__aenter__.return_value = second_session
    second_ctx.__aexit__.return_value = None

    with (
        patch(
            "intentkit.core.credit.refill.get_session", side_effect=[first_ctx, second_ctx]
        ),
        patch(
            "intentkit.core.credit.refill.CreditAccount.model_validate",
            return_value=account,
        ),
        patch(
            "intentkit.core.credit.refill.refill_free_credits_for_account",
            new_callable=AsyncMock,
        ) as mock_refill,
    ):
        await refill_all_free_credits()

    mock_refill.assert_called_once_with(second_session, account)
