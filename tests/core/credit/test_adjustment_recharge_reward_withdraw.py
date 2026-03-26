from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.core.credit.adjustment import adjustment
from intentkit.core.credit.recharge import recharge
from intentkit.core.credit.reward import reward
from intentkit.core.credit.withdraw import withdraw
from intentkit.models.agent import Agent
from intentkit.models.credit import (
    CreditAccount,
    CreditAccountTable,
    CreditType,
    RewardType,
)
from intentkit.utils.error import IntentKitAPIError

# ==============================================================================
# Adjustment tests
# ==============================================================================


@pytest.mark.asyncio
async def test_adjustment_positive_success():
    """Test positive adjustment uses income for user and deduction for platform."""
    user_id = "user_1"
    amount = Decimal("10.0000")
    upstream_tx_id = "tx_adj_pos"
    note = "Positive adjustment"

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
            "intentkit.models.credit.CreditAccount.income_in_session",
            new_callable=AsyncMock,
        ) as mock_income,
        patch(
            "intentkit.models.credit.CreditAccount.deduction_in_session",
            new_callable=AsyncMock,
        ) as mock_deduction,
    ):
        mock_income.return_value = mock_user_account
        mock_deduction.return_value = mock_platform_account

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        result = await adjustment(
            mock_session, user_id, CreditType.PERMANENT, amount, upstream_tx_id, note
        )

        assert result == mock_user_account

        # Positive amount: income for user
        mock_income.assert_called_once()
        assert mock_income.call_args[1]["owner_id"] == user_id
        assert mock_income.call_args[1]["amount_details"] == {
            CreditType.PERMANENT: amount
        }

        # Positive amount: deduction for platform
        mock_deduction.assert_called_once()
        assert mock_deduction.call_args[1]["owner_id"] == "platform_adjustment"

        mock_session.flush.assert_called_once()
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_adjustment_negative_success():
    """Test negative adjustment uses deduction for user and income for platform."""
    user_id = "user_1"
    amount = Decimal("-5.0000")
    upstream_tx_id = "tx_adj_neg"
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
        result = await adjustment(
            mock_session, user_id, CreditType.PERMANENT, amount, upstream_tx_id, note
        )

        assert result == mock_user_account

        # Negative amount: deduction for user (with positive abs amount)
        mock_deduction.assert_called_once()
        assert mock_deduction.call_args[1]["owner_id"] == user_id
        assert mock_deduction.call_args[1]["amount"] == Decimal("5.0000")

        # Negative amount: income for platform
        mock_income.assert_called_once()
        assert mock_income.call_args[1]["owner_id"] == "platform_adjustment"

        mock_session.flush.assert_called_once()
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_adjustment_zero_amount_raises():
    """Test adjustment with zero amount raises ValueError."""
    with patch(
        "intentkit.models.credit.CreditEvent.check_upstream_tx_id_exists",
        new_callable=AsyncMock,
    ):
        with pytest.raises(ValueError, match="Adjustment amount cannot be zero"):
            await adjustment(
                AsyncMock(),
                "user_1",
                CreditType.PERMANENT,
                Decimal("0"),
                "tx_zero",
                "Zero adjustment",
            )


@pytest.mark.asyncio
async def test_adjustment_empty_note_raises():
    """Test adjustment with empty note raises ValueError."""
    with patch(
        "intentkit.models.credit.CreditEvent.check_upstream_tx_id_exists",
        new_callable=AsyncMock,
    ):
        with pytest.raises(
            ValueError, match="Adjustment requires a note explaining the reason"
        ):
            await adjustment(
                AsyncMock(),
                "user_1",
                CreditType.PERMANENT,
                Decimal("5.0000"),
                "tx_no_note",
                "",
            )


@pytest.mark.asyncio
async def test_adjustment_free_credit_type():
    """Test adjustment with FREE credit type sets correct credit fields."""
    user_id = "user_1"
    amount = Decimal("10.0000")
    upstream_tx_id = "tx_adj_free"
    note = "Free credit adjustment"

    mock_user_account = MagicMock(spec=CreditAccountTable)
    mock_user_account.id = "acc_user"
    mock_user_account.credits = Decimal("0")
    mock_user_account.free_credits = Decimal("10")
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
        mock_income.return_value = mock_user_account
        mock_deduction.return_value = mock_platform_account

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        result = await adjustment(
            mock_session, user_id, CreditType.FREE, amount, upstream_tx_id, note
        )

        assert result == mock_user_account

        # Verify income called with FREE credit type
        mock_income.assert_called_once()
        assert mock_income.call_args[1]["amount_details"] == {CreditType.FREE: amount}

        # Verify deduction called with FREE credit type
        mock_deduction.assert_called_once()
        assert mock_deduction.call_args[1]["credit_type"] == CreditType.FREE


@pytest.mark.asyncio
async def test_adjustment_reward_credit_type():
    """Test adjustment with REWARD credit type sets correct credit fields."""
    user_id = "user_1"
    amount = Decimal("10.0000")
    upstream_tx_id = "tx_adj_reward"
    note = "Reward credit adjustment"

    mock_user_account = MagicMock(spec=CreditAccountTable)
    mock_user_account.id = "acc_user"
    mock_user_account.credits = Decimal("0")
    mock_user_account.free_credits = Decimal("0")
    mock_user_account.reward_credits = Decimal("10")

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
        mock_income.return_value = mock_user_account
        mock_deduction.return_value = mock_platform_account

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        result = await adjustment(
            mock_session, user_id, CreditType.REWARD, amount, upstream_tx_id, note
        )

        assert result == mock_user_account

        # Verify income called with REWARD credit type
        mock_income.assert_called_once()
        assert mock_income.call_args[1]["amount_details"] == {CreditType.REWARD: amount}

        # Verify deduction called with REWARD credit type
        mock_deduction.assert_called_once()
        assert mock_deduction.call_args[1]["credit_type"] == CreditType.REWARD


# ==============================================================================
# Recharge tests
# ==============================================================================


@pytest.mark.asyncio
async def test_recharge_negative_amount_raises():
    """Test recharge with negative amount raises ValueError."""
    with patch(
        "intentkit.models.credit.CreditEvent.check_upstream_tx_id_exists",
        new_callable=AsyncMock,
    ):
        with pytest.raises(ValueError, match="Recharge amount must be positive"):
            await recharge(AsyncMock(), "user_1", Decimal("-10.0"), "tx_neg")


@pytest.mark.asyncio
async def test_recharge_zero_amount_raises():
    """Test recharge with zero amount raises ValueError."""
    with patch(
        "intentkit.models.credit.CreditEvent.check_upstream_tx_id_exists",
        new_callable=AsyncMock,
    ):
        with pytest.raises(ValueError, match="Recharge amount must be positive"):
            await recharge(AsyncMock(), "user_1", Decimal("0"), "tx_zero")


@pytest.mark.asyncio
async def test_recharge_creates_correct_transactions():
    """Test recharge creates correct event and transaction objects in session."""
    user_id = "user_1"
    amount = Decimal("100.0000")
    upstream_tx_id = "tx_recharge"
    note = "Test recharge"

    mock_user_account = MagicMock(spec=CreditAccountTable)
    mock_user_account.id = "acc_user"
    mock_user_account.credits = Decimal("100")
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

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        result = await recharge(mock_session, user_id, amount, upstream_tx_id, note)

        assert result == mock_user_account

        # Should add event + 2 transactions = 3 session.add calls
        assert mock_session.add.call_count == 3

        mock_session.flush.assert_called_once()
        mock_session.commit.assert_called_once()

        # Verify income called with PERMANENT credit type
        mock_income.assert_called_once()
        assert mock_income.call_args[1]["amount_details"] == {
            CreditType.PERMANENT: amount
        }

        # Verify deduction called for platform
        mock_deduction.assert_called_once()

        # Verify slack notification sent
        mock_slack.assert_called_once()


# ==============================================================================
# Reward tests
# ==============================================================================


@pytest.mark.asyncio
async def test_reward_success():
    """Test successful reward with REWARD type income and platform deduction."""
    user_id = "user_1"
    amount = Decimal("10.0000")
    upstream_tx_id = "tx_reward"

    mock_user_account = MagicMock(spec=CreditAccountTable)
    mock_user_account.id = "acc_user"
    mock_user_account.credits = Decimal("0")
    mock_user_account.free_credits = Decimal("0")
    mock_user_account.reward_credits = Decimal("10")

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
        result = await reward(mock_session, user_id, amount, upstream_tx_id)

        assert result == mock_user_account

        # Verify user income with REWARD type
        mock_income.assert_called_once()
        assert mock_income.call_args[1]["amount_details"] == {CreditType.REWARD: amount}

        # Verify platform deduction
        mock_deduction.assert_called_once()

        mock_session.flush.assert_called_once()
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_reward_negative_amount_raises():
    """Test reward with negative amount raises ValueError."""
    with patch(
        "intentkit.models.credit.CreditEvent.check_upstream_tx_id_exists",
        new_callable=AsyncMock,
    ):
        with pytest.raises(ValueError, match="Reward amount must be positive"):
            await reward(AsyncMock(), "user_1", Decimal("-5.0"), "tx_neg_reward")


@pytest.mark.asyncio
async def test_reward_zero_amount_raises():
    """Test reward with zero amount raises ValueError."""
    with patch(
        "intentkit.models.credit.CreditEvent.check_upstream_tx_id_exists",
        new_callable=AsyncMock,
    ):
        with pytest.raises(ValueError, match="Reward amount must be positive"):
            await reward(AsyncMock(), "user_1", Decimal("0"), "tx_zero_reward")


@pytest.mark.asyncio
async def test_reward_custom_reward_type():
    """Test reward with custom reward_type parameter is used in event."""
    user_id = "user_1"
    amount = Decimal("25.0000")
    upstream_tx_id = "tx_event_reward"

    mock_user_account = MagicMock(spec=CreditAccountTable)
    mock_user_account.id = "acc_user"
    mock_user_account.credits = Decimal("0")
    mock_user_account.free_credits = Decimal("0")
    mock_user_account.reward_credits = Decimal("25")

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
        result = await reward(
            mock_session,
            user_id,
            amount,
            upstream_tx_id,
            reward_type=RewardType.EVENT_REWARD,
        )

        assert result == mock_user_account

        # Verify income called with REWARD credit type
        mock_income.assert_called_once()
        assert mock_income.call_args[1]["amount_details"] == {CreditType.REWARD: amount}

        # Verify platform deduction
        mock_deduction.assert_called_once()

        # Should add event + 2 transactions = 3 session.add calls
        assert mock_session.add.call_count == 3


# ==============================================================================
# Withdraw tests
# ==============================================================================


@pytest.mark.asyncio
async def test_withdraw_success():
    """Test successful withdraw: deduction from agent, income to platform."""
    agent_id = "agent_1"
    user_id = "user_1"
    amount = Decimal("50.0000")
    upstream_tx_id = "tx_withdraw"

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

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        result = await withdraw(mock_session, agent_id, amount, upstream_tx_id)

        assert result == mock_updated_agent_account

        # Verify deduction from agent
        mock_deduction.assert_called_once()
        assert mock_deduction.call_args[1]["owner_id"] == agent_id
        assert mock_deduction.call_args[1]["amount"] == amount

        # Verify income to platform
        mock_income.assert_called_once()

        mock_session.flush.assert_called_once()
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_withdraw_negative_amount_raises():
    """Test withdraw with negative amount raises ValueError."""
    with patch(
        "intentkit.models.credit.CreditEvent.check_upstream_tx_id_exists",
        new_callable=AsyncMock,
    ):
        with pytest.raises(ValueError, match="Withdraw amount must be positive"):
            await withdraw(AsyncMock(), "agent_1", Decimal("-10.0"), "tx_neg_withdraw")


@pytest.mark.asyncio
async def test_withdraw_zero_amount_raises():
    """Test withdraw with zero amount raises ValueError."""
    with patch(
        "intentkit.models.credit.CreditEvent.check_upstream_tx_id_exists",
        new_callable=AsyncMock,
    ):
        with pytest.raises(ValueError, match="Withdraw amount must be positive"):
            await withdraw(AsyncMock(), "agent_1", Decimal("0"), "tx_zero_withdraw")


@pytest.mark.asyncio
async def test_withdraw_agent_not_found():
    """Test withdraw raises IntentKitAPIError(404) when agent not found."""
    with (
        patch(
            "intentkit.models.credit.CreditEvent.check_upstream_tx_id_exists",
            new_callable=AsyncMock,
        ),
        patch(
            "intentkit.core.credit.withdraw.get_agent", new_callable=AsyncMock
        ) as mock_get_agent,
    ):
        mock_get_agent.return_value = None

        with pytest.raises(IntentKitAPIError) as exc_info:
            await withdraw(
                AsyncMock(), "nonexistent_agent", Decimal("10.0"), "tx_no_agent"
            )
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_withdraw_agent_no_owner():
    """Test withdraw raises IntentKitAPIError(400) when agent has no owner."""
    mock_agent = MagicMock(spec=Agent)
    mock_agent.id = "agent_1"
    mock_agent.owner = None

    with (
        patch(
            "intentkit.models.credit.CreditEvent.check_upstream_tx_id_exists",
            new_callable=AsyncMock,
        ),
        patch(
            "intentkit.core.credit.withdraw.get_agent", new_callable=AsyncMock
        ) as mock_get_agent,
    ):
        mock_get_agent.return_value = mock_agent

        with pytest.raises(IntentKitAPIError) as exc_info:
            await withdraw(AsyncMock(), "agent_1", Decimal("10.0"), "tx_no_owner")
        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_withdraw_insufficient_balance():
    """Test withdraw raises IntentKitAPIError(400) when insufficient balance."""
    agent_id = "agent_1"
    amount = Decimal("200.0000")

    mock_agent = MagicMock(spec=Agent)
    mock_agent.id = agent_id
    mock_agent.owner = "user_1"

    mock_agent_account = MagicMock(spec=CreditAccount)
    mock_agent_account.id = "acc_agent"
    mock_agent_account.credits = Decimal("50.0000")  # Less than requested amount
    mock_agent_account.free_credits = Decimal("0")
    mock_agent_account.reward_credits = Decimal("0")

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
    ):
        mock_get_agent.return_value = mock_agent
        mock_get_account.return_value = mock_agent_account

        with pytest.raises(IntentKitAPIError) as exc_info:
            await withdraw(AsyncMock(), agent_id, amount, "tx_insufficient")
        assert exc_info.value.status_code == 400
