from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.config.config import config
from intentkit.core.credit import (
    expense_message,
    expense_summarize,
    skill_cost,
)
from intentkit.models.agent import Agent
from intentkit.models.credit import (
    CreditAccountTable,
)


@pytest.mark.asyncio
async def test_expense_message_soft_off():
    """Test expense_message with payment disabled (soft off)."""
    user_id = "user_1"
    message_id = "msg_1"
    start_message_id = "start_1"
    base_llm_amount = Decimal("0.0100")
    agent = MagicMock(spec=Agent)
    agent.id = "agent_1"
    agent.owner = "owner_1"
    agent.fee_percentage = Decimal("10.0")
    agent.model = "gpt-4"

    mock_user_account = MagicMock(spec=CreditAccountTable)
    mock_user_account.id = "acc_user"
    mock_user_account.credits = Decimal("100.0000")
    mock_user_account.free_credits = Decimal("0")
    mock_user_account.reward_credits = Decimal("0")

    mock_agent_data = MagicMock()
    mock_agent_data.evm_wallet_address = "0x123"

    def side_effect_refresh(instance):
        instance.created_at = datetime.now()

    with (
        patch.object(config, "payment_enabled", False),
        patch(
            "intentkit.core.credit.CreditEvent.check_upstream_tx_id_exists",
            new_callable=AsyncMock,
        ),
        patch(
            "intentkit.core.credit.CreditAccount.get_or_create_in_session",
            new_callable=AsyncMock,
        ) as mock_get_or_create,
        patch(
            "intentkit.core.credit.CreditAccount.expense_in_session",
            new_callable=AsyncMock,
        ) as mock_expense,
        patch(
            "intentkit.models.agent_data.AgentQuota.add_free_income_in_session",
            new_callable=AsyncMock,
        ) as mock_add_free,
        patch(
            "intentkit.core.credit.AppSetting.payment", new_callable=AsyncMock
        ) as mock_payment_settings,
        patch(
            "intentkit.core.credit.AgentData.get", new_callable=AsyncMock
        ) as mock_agent_data_get,
    ):
        mock_payment_settings.return_value.fee_platform_percentage = Decimal("20.0")
        mock_get_or_create.return_value = mock_user_account
        mock_agent_data_get.return_value = mock_agent_data

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.refresh.side_effect = side_effect_refresh

        # Run
        await expense_message(
            mock_session, user_id, message_id, start_message_id, base_llm_amount, agent
        )

        # Verify
        # Should call get_or_create instead of expense because amount is 0
        mock_get_or_create.assert_called_once()
        mock_expense.assert_not_called()
        mock_add_free.assert_not_called()

        # Check CreditEvent creation
        # We can inspect the calls to session.add to find the CreditEvent
        added_objects = [call.args[0] for call in mock_session.add.call_args_list]
        event = next(
            (
                obj
                for obj in added_objects
                if hasattr(obj, "event_type") and obj.event_type == "message"
            ),
            None,
        )
        assert event is not None
        assert event.base_original_amount == base_llm_amount
        assert event.base_discount_amount == base_llm_amount
        assert event.base_amount == Decimal("0")
        assert event.total_amount == Decimal("0")

        # Verify no transactions created
        transactions = [obj for obj in added_objects if hasattr(obj, "tx_type")]
        assert len(transactions) == 0


@pytest.mark.asyncio
async def test_expense_message_enabled():
    """Test expense_message with payment enabled."""
    user_id = "user_1"
    message_id = "msg_1"
    start_message_id = "start_1"
    base_llm_amount = Decimal("0.0100")
    agent = MagicMock(spec=Agent)
    agent.id = "agent_1"
    agent.owner = "owner_1"
    agent.fee_percentage = Decimal("10.0")
    agent.model = "gpt-4"

    mock_user_account = MagicMock(spec=CreditAccountTable)
    mock_user_account.id = "acc_user"
    mock_user_account.credits = Decimal("100.0000")
    mock_user_account.free_credits = Decimal("0")
    mock_user_account.reward_credits = Decimal("0")

    mock_agent_data = MagicMock()
    mock_agent_data.evm_wallet_address = "0x123"

    # Mock return value for income_in_session
    mock_income_account = MagicMock()
    mock_income_account.id = "acc_income"

    def side_effect_refresh(instance):
        instance.created_at = datetime.now()

    with (
        patch.object(config, "payment_enabled", True),
        patch(
            "intentkit.core.credit.CreditEvent.check_upstream_tx_id_exists",
            new_callable=AsyncMock,
        ),
        patch(
            "intentkit.core.credit.CreditAccount.get_or_create_in_session",
            new_callable=AsyncMock,
        ) as mock_get_or_create,
        patch(
            "intentkit.core.credit.CreditAccount.expense_in_session",
            new_callable=AsyncMock,
        ) as mock_expense,
        patch(
            "intentkit.models.agent_data.AgentQuota.add_free_income_in_session",
            new_callable=AsyncMock,
        ),
        patch(
            "intentkit.core.credit.AppSetting.payment", new_callable=AsyncMock
        ) as mock_payment_settings,
        patch(
            "intentkit.core.credit.AgentData.get", new_callable=AsyncMock
        ) as mock_agent_data_get,
        patch(
            "intentkit.core.credit.CreditAccount.income_in_session",
            new_callable=AsyncMock,
        ) as mock_income,
    ):
        mock_payment_settings.return_value.fee_platform_percentage = Decimal("20.0")
        mock_expense.return_value = (
            mock_user_account,
            {},
        )  # Return account and details
        mock_agent_data_get.return_value = mock_agent_data
        mock_income.return_value = mock_income_account

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.refresh.side_effect = side_effect_refresh

        # Run
        await expense_message(
            mock_session, user_id, message_id, start_message_id, base_llm_amount, agent
        )

        # Verify
        mock_expense.assert_called_once()
        mock_get_or_create.assert_not_called()

        added_objects = [call.args[0] for call in mock_session.add.call_args_list]
        event = next(
            (
                obj
                for obj in added_objects
                if hasattr(obj, "event_type") and obj.event_type == "message"
            ),
            None,
        )
        assert event is not None
        assert event.base_original_amount == base_llm_amount
        assert event.base_discount_amount == Decimal("0")
        # base_amount should be > 0
        assert event.base_amount == base_llm_amount
        assert event.total_amount > Decimal("0")

        # Verify transactions created
        transactions = [obj for obj in added_objects if hasattr(obj, "tx_type")]
        assert len(transactions) > 0


@pytest.mark.asyncio
async def test_skill_cost_soft_off():
    """Test skill_cost with payment disabled."""
    skill_name = "test_skill"
    user_id = "user_1"
    agent = MagicMock(spec=Agent)
    agent.id = "agent_1"
    agent.owner = "owner_1"
    agent.fee_percentage = Decimal("10.0")
    agent.skills = {}  # Fix: explicitly set skills to empty dict

    with (
        patch.object(config, "payment_enabled", False),
        patch(
            "intentkit.core.credit.AppSetting.payment", new_callable=AsyncMock
        ) as mock_payment_settings,
        patch(
            "intentkit.core.credit.Skill.get", new_callable=AsyncMock
        ) as mock_skill_get,
    ):
        # We need to mock Skill.get to return a mock skill with a price
        mock_skill = MagicMock()
        mock_skill.price = Decimal("1.0000")
        mock_skill.author = "dev_1"
        mock_skill.category = "test_cat"
        mock_skill_get.return_value = mock_skill

        mock_payment_settings.return_value.fee_platform_percentage = Decimal("20.0")
        mock_payment_settings.return_value.fee_dev_percentage = Decimal(
            "10.0"
        )  # Added default

        cost_info = await skill_cost(skill_name, user_id, agent)

        assert cost_info.base_original_amount == Decimal("1.0000")
        assert cost_info.base_discount_amount == Decimal("1.0000")
        assert cost_info.base_amount == Decimal("0")
        assert cost_info.total_amount == Decimal("0")
        assert cost_info.fee_platform_amount == Decimal("0")


@pytest.mark.asyncio
async def test_expense_summarize_soft_off():
    """Test expense_summarize with payment disabled."""
    user_id = "user_1"
    message_id = "msg_sum_1"
    start_message_id = "start_1"
    base_llm_amount = Decimal("0.0500")
    agent = MagicMock(spec=Agent)
    agent.id = "agent_1"
    agent.owner = "owner_1"
    agent.fee_percentage = Decimal("10.0")
    agent.model = "gpt-4"

    mock_user_account = MagicMock(spec=CreditAccountTable)
    mock_user_account.id = "acc_user"
    mock_user_account.credits = Decimal("100.0000")
    mock_user_account.free_credits = Decimal("0")
    mock_user_account.reward_credits = Decimal("0")

    mock_agent_data = MagicMock()
    mock_agent_data.evm_wallet_address = "0x123"

    def side_effect_refresh(instance):
        instance.created_at = datetime.now()

    with (
        patch.object(config, "payment_enabled", False),
        patch(
            "intentkit.core.credit.CreditEvent.check_upstream_tx_id_exists",
            new_callable=AsyncMock,
        ),
        patch(
            "intentkit.core.credit.CreditAccount.get_or_create_in_session",
            new_callable=AsyncMock,
        ) as mock_get_or_create,
        patch(
            "intentkit.core.credit.CreditAccount.expense_in_session",
            new_callable=AsyncMock,
        ) as mock_expense,
        patch(
            "intentkit.core.credit.AppSetting.payment", new_callable=AsyncMock
        ) as mock_payment_settings,
        patch(
            "intentkit.core.credit.AgentData.get", new_callable=AsyncMock
        ) as mock_agent_data_get,
    ):
        mock_payment_settings.return_value.fee_platform_percentage = Decimal("20.0")
        mock_get_or_create.return_value = mock_user_account
        mock_agent_data_get.return_value = mock_agent_data

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.refresh.side_effect = side_effect_refresh

        await expense_summarize(
            mock_session, user_id, message_id, start_message_id, base_llm_amount, agent
        )

        mock_get_or_create.assert_called_once()
        mock_expense.assert_not_called()

        added_objects = [call.args[0] for call in mock_session.add.call_args_list]
        event = next(
            (
                obj
                for obj in added_objects
                if hasattr(obj, "event_type") and obj.event_type == "memory"
            ),
            None,
        )
        assert event is not None
        assert event.base_discount_amount == base_llm_amount
        assert event.total_amount == Decimal("0")

        transactions = [obj for obj in added_objects if hasattr(obj, "tx_type")]
        assert len(transactions) == 0
