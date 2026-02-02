from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.core.credit import (
    adjustment,
    recharge,
    reward,
    withdraw,
)
from intentkit.models.agent import Agent
from intentkit.models.credit import (
    CreditAccount,
    CreditAccountTable,
    CreditType,
)


@pytest.mark.asyncio
async def test_recharge_success():
    """Test successful credit recharge."""
    # Setup
    user_id = "user_1"
    amount = Decimal("100.0000")
    upstream_tx_id = "tx_123"
    note = "Test recharge"

    mock_user_account = MagicMock(spec=CreditAccountTable)
    mock_user_account.id = "acc_user"
    mock_user_account.credits = Decimal("0")
    mock_user_account.free_credits = Decimal("0")
    mock_user_account.reward_credits = Decimal("0")

    mock_platform_account = MagicMock(spec=CreditAccountTable)
    mock_platform_account.id = "acc_platform"

    with (
        patch(
            "intentkit.models.credit.CreditEvent.check_upstream_tx_id_exists",
            new_callable=AsyncMock,
        ),
        patch(
            "intentkit.models.credit.CreditAccount.income_in_session",
            new_callable=AsyncMock,
        ) as mock_income,
        patch(
            "intentkit.models.credit.CreditAccount.deduction_in_session",
            new_callable=AsyncMock,
        ) as mock_deduction,
        patch("intentkit.core.credit.recharge.send_alert") as mock_slack,
    ):
        mock_income.return_value = mock_user_account
        mock_deduction.return_value = mock_platform_account

        # Run
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        result = await recharge(mock_session, user_id, amount, upstream_tx_id, note)

        # Verify
        assert result == mock_user_account

        # Check income called for user
        mock_income.assert_called_once()
        assert mock_income.call_args[1]["owner_id"] == user_id
        assert mock_income.call_args[1]["amount_details"] == {
            CreditType.PERMANENT: amount
        }

        # Check deduction called for platform
        mock_deduction.assert_called_once()

        # Check database commits
        mock_session.add.assert_called()  # Should add event and transactions
        mock_session.flush.assert_called_once()
        mock_session.commit.assert_called_once()

        # Check slack notification
        mock_slack.assert_called_once()


@pytest.mark.asyncio
async def test_recharge_negative_amount():
    """Test recharge with negative amount fails."""
    with patch(
        "intentkit.models.credit.CreditEvent.check_upstream_tx_id_exists",
        new_callable=AsyncMock,
    ):
        with pytest.raises(ValueError, match="Recharge amount must be positive"):
            _ = await recharge(AsyncMock(), "user_1", Decimal("-10.0"), "tx_123")


@pytest.mark.asyncio
async def test_withdraw_success():
    """Test successful credit withdraw."""
    # Setup
    agent_id = "agent_1"
    user_id = "user_1"
    amount = Decimal("50.0000")
    upstream_tx_id = "tx_456"

    mock_agent = MagicMock(spec=Agent)
    mock_agent.id = agent_id
    mock_agent.owner = user_id

    mock_agent_account = MagicMock(spec=CreditAccount)
    mock_agent_account.id = "acc_agent"
    mock_agent_account.credits = Decimal("100.0000")
    mock_agent_account.free_credits = Decimal("0")
    mock_agent_account.reward_credits = Decimal("0")

    mock_updated_agent_account = MagicMock(spec=CreditAccountTable)
    mock_updated_agent_account.id = "acc_agent"
    mock_updated_agent_account.credits = Decimal("50.0000")
    mock_updated_agent_account.free_credits = Decimal("0")
    mock_updated_agent_account.reward_credits = Decimal("0")

    mock_platform_account = MagicMock(spec=CreditAccountTable)
    mock_platform_account.id = "acc_platform"

    with (
        patch(
            "intentkit.models.credit.CreditEvent.check_upstream_tx_id_exists",
            new_callable=AsyncMock,
        ),
        patch(
            "intentkit.core.credit.withdraw.get_agent", new_callable=AsyncMock
        ) as mock_get_agent,
        patch("intentkit.models.agent_data.AgentData.get", new_callable=AsyncMock),
        patch(
            "intentkit.models.credit.CreditAccount.get_in_session",
            new_callable=AsyncMock,
        ) as mock_get_account,
        patch(
            "intentkit.models.credit.CreditAccount.deduction_in_session",
            new_callable=AsyncMock,
        ) as mock_deduction,
        patch(
            "intentkit.models.credit.CreditAccount.income_in_session",
            new_callable=AsyncMock,
        ) as mock_income,
        patch("intentkit.core.credit.withdraw.send_alert"),
    ):
        mock_get_agent.return_value = mock_agent
        mock_get_account.return_value = mock_agent_account
        mock_deduction.return_value = mock_updated_agent_account
        mock_income.return_value = mock_platform_account

        # Run
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        result = await withdraw(mock_session, agent_id, amount, upstream_tx_id)

        assert result == mock_updated_agent_account

        # Check deduction from agent
        mock_deduction.assert_called_once()
        assert mock_deduction.call_args[1]["owner_id"] == agent_id
        assert mock_deduction.call_args[1]["amount"] == amount

        # Check income to platform
        mock_income.assert_called_once()


@pytest.mark.asyncio
async def test_reward_success():
    """Test successful reward crediting."""
    user_id = "user_1"
    amount = Decimal("10.0000")
    upstream_tx_id = "tx_789"

    mock_user_account = MagicMock(spec=CreditAccountTable)
    mock_user_account.id = "acc_user"
    mock_user_account.credits = Decimal("0")
    mock_user_account.free_credits = Decimal("0")
    mock_user_account.reward_credits = Decimal("0")

    mock_platform_account = MagicMock(spec=CreditAccountTable)
    mock_platform_account.id = "acc_platform"

    with (
        patch(
            "intentkit.models.credit.CreditEvent.check_upstream_tx_id_exists",
            new_callable=AsyncMock,
        ),
        patch(
            "intentkit.models.credit.CreditAccount.income_in_session",
            new_callable=AsyncMock,
        ) as mock_income,
        patch(
            "intentkit.models.credit.CreditAccount.deduction_in_session",
            new_callable=AsyncMock,
        ) as mock_deduction,
        patch("intentkit.core.credit.reward.send_alert"),
    ):
        mock_income.return_value = mock_user_account
        mock_deduction.return_value = mock_platform_account

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        _ = await reward(mock_session, user_id, amount, upstream_tx_id)

        # Check user income (reward type)
        mock_income.assert_called_once()
        assert mock_income.call_args[1]["amount_details"] == {CreditType.REWARD: amount}

        # Check platform deduction
        mock_deduction.assert_called_once()


@pytest.mark.asyncio
async def test_adjustment_income():
    """Test positive adjustment (income)."""
    user_id = "user_1"
    amount = Decimal("5.0000")
    upstream_tx_id = "tx_adj_1"
    note = "Refund"

    mock_user_account = MagicMock(spec=CreditAccountTable)
    mock_user_account.id = "acc_user"
    mock_user_account.credits = Decimal("0")
    mock_user_account.free_credits = Decimal("0")
    mock_user_account.reward_credits = Decimal("0")

    mock_platform_account = MagicMock(spec=CreditAccountTable)
    mock_platform_account.id = "acc_platform"

    with (
        patch(
            "intentkit.models.credit.CreditEvent.check_upstream_tx_id_exists",
            new_callable=AsyncMock,
        ),
        patch(
            "intentkit.models.credit.CreditAccount.income_in_session",
            new_callable=AsyncMock,
        ) as mock_income,
        patch(
            "intentkit.models.credit.CreditAccount.deduction_in_session",
            new_callable=AsyncMock,
        ) as mock_deduction,
    ):
        # For income: user gets income, platform gets deduction
        mock_income.return_value = mock_user_account  # First call for user
        mock_deduction.return_value = mock_platform_account  # Second call for platform

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        _ = await adjustment(
            mock_session, user_id, CreditType.PERMANENT, amount, upstream_tx_id, note
        )

        # Verify user income
        assert mock_income.call_count == 1
        assert mock_income.call_args[1]["owner_id"] == user_id

        # Verify platform deduction
        assert mock_deduction.call_count == 1
        assert mock_deduction.call_args[1]["owner_id"] == "platform_adjustment"


@pytest.mark.asyncio
async def test_adjustment_expense():
    """Test negative adjustment (expense)."""
    user_id = "user_1"
    amount = Decimal("-5.0000")
    upstream_tx_id = "tx_adj_2"
    note = "Correction"

    mock_user_account = MagicMock(spec=CreditAccountTable)
    mock_user_account.id = "acc_user"
    mock_user_account.credits = Decimal("10")
    mock_user_account.free_credits = Decimal("0")
    mock_user_account.reward_credits = Decimal("0")

    mock_platform_account = MagicMock(spec=CreditAccountTable)
    mock_platform_account.id = "acc_platform"

    with (
        patch(
            "intentkit.models.credit.CreditEvent.check_upstream_tx_id_exists",
            new_callable=AsyncMock,
        ),
        patch(
            "intentkit.models.credit.CreditAccount.deduction_in_session",
            new_callable=AsyncMock,
        ) as mock_deduction,
        patch(
            "intentkit.models.credit.CreditAccount.income_in_session",
            new_callable=AsyncMock,
        ) as mock_income,
    ):
        mock_deduction.return_value = mock_user_account
        mock_income.return_value = mock_platform_account

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        _ = await adjustment(
            mock_session, user_id, CreditType.PERMANENT, amount, upstream_tx_id, note
        )

        # Verify user deduction (using positive amount)
        assert mock_deduction.call_count == 1
        assert mock_deduction.call_args[1]["owner_id"] == user_id
        assert mock_deduction.call_args[1]["amount"] == Decimal("5.0000")

        # Verify platform income
        assert mock_income.call_count == 1
