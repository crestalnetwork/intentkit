from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.core.credit import (
    expense_media,
    expense_skill,
    expense_summarize,
    skill_cost,
)
from intentkit.models.agent import Agent
from intentkit.models.credit import CreditAccountTable, CreditType
from intentkit.models.credit.event import EventType, UpstreamType
from intentkit.models.credit.transaction import TransactionType


@pytest.mark.asyncio
async def test_skill_cost_basic_pricing():
    agent = MagicMock(spec=Agent)
    agent.id = "agent-1"
    agent.owner = "user-1"
    agent.team_id = "team-1"
    agent.fee_percentage = Decimal("0")
    agent.skills = {}

    with (
        patch("intentkit.config.config.config.payment_enabled", True),
        patch(
            "intentkit.models.app_setting.AppSetting.payment", new_callable=AsyncMock
        ) as mock_payment,
    ):
        mock_payment.return_value.fee_platform_percentage = Decimal("0")

        cost = await skill_cost(Decimal("1.0000"), "team-2", agent)

    assert cost.base_skill_amount == Decimal("1.0000")
    assert cost.total_amount == Decimal("1.0000")


@pytest.mark.asyncio
async def test_skill_cost_with_platform_fee():
    agent = MagicMock(spec=Agent)
    agent.id = "agent-1"
    agent.owner = "user-1"
    agent.team_id = "team-1"
    agent.fee_percentage = Decimal("0")
    agent.skills = {}

    with (
        patch("intentkit.config.config.config.payment_enabled", True),
        patch(
            "intentkit.models.app_setting.AppSetting.payment", new_callable=AsyncMock
        ) as mock_payment,
    ):
        mock_payment.return_value.fee_platform_percentage = Decimal("100")

        cost = await skill_cost(Decimal("1.0000"), "team-2", agent)

    assert cost.base_skill_amount == Decimal("1.0000")
    assert cost.fee_platform_amount == Decimal("1.0000")
    assert cost.total_amount == Decimal("2.0000")


@pytest.mark.asyncio
async def test_expense_skill_creates_transactions():
    agent = MagicMock(spec=Agent)
    agent.id = "agent-1"
    agent.owner = "owner-1"
    agent.team_id = "team-1"
    agent.fee_percentage = Decimal("10.0")

    skill_cost_info = MagicMock()
    skill_cost_info.total_amount = Decimal("5.0000")
    skill_cost_info.base_amount = Decimal("4.0000")
    skill_cost_info.base_original_amount = Decimal("4.0000")
    skill_cost_info.base_discount_amount = Decimal("0")
    skill_cost_info.base_skill_amount = Decimal("4.0000")
    skill_cost_info.fee_platform_amount = Decimal("0.5000")
    skill_cost_info.fee_agent_amount = Decimal("0.5000")

    mock_user_account = MagicMock(spec=CreditAccountTable)
    mock_user_account.id = "acc-user"
    mock_user_account.credits = Decimal("10.0")
    mock_user_account.free_credits = Decimal("0")
    mock_user_account.reward_credits = Decimal("0")

    mock_income_account = MagicMock(spec=CreditAccountTable)
    mock_income_account.id = "acc-income"

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    def side_effect_refresh(instance):
        instance.created_at = datetime.now()

    mock_session.refresh.side_effect = side_effect_refresh

    with (
        patch(
            "intentkit.core.credit.expense.skill_cost", new_callable=AsyncMock
        ) as mock_skill_cost,
        patch(
            "intentkit.models.credit.CreditEvent.check_upstream_tx_id_exists",
            new_callable=AsyncMock,
        ),
        patch(
            "intentkit.models.credit.CreditAccount.expense_in_session",
            new_callable=AsyncMock,
        ) as mock_expense,
        patch(
            "intentkit.models.credit.CreditAccount.income_in_session",
            new_callable=AsyncMock,
            return_value=mock_income_account,
        ) as mock_income,
        patch(
            "intentkit.models.agent_data.AgentQuota.add_free_income_in_session",
            new_callable=AsyncMock,
        ) as mock_add_free,
        patch(
            "intentkit.models.agent_data.AgentData.get",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        mock_skill_cost.return_value = skill_cost_info
        mock_expense.return_value = (
            mock_user_account,
            {CreditType.PERMANENT: Decimal("5.0000")},
        )

        result = await expense_skill(
            mock_session,
            team_id="team-1",
            message_id="msg-1",
            start_message_id="start-1",
            skill_call_id="skill-1",
            skill_name="skill-name",
            price=Decimal("4.0000"),
            agent=agent,
            user_id="user-1",
        )

    assert result.event_type == "skill_call"
    mock_expense.assert_called_once()
    mock_income.assert_called()
    mock_add_free.assert_not_called()

    added_objects = [call.args[0] for call in mock_session.add.call_args_list]
    transactions = [obj for obj in added_objects if hasattr(obj, "tx_type")]
    # Should have: user debit, skill credit, platform credit, agent credit (no dev tx)
    assert len(transactions) >= 3


@pytest.mark.asyncio
async def test_expense_summarize_with_payment_enabled_creates_transactions():
    team_id = "team-1"
    message_id = "msg-1"
    start_message_id = "start-1"
    base_llm_amount = Decimal("0.0100")

    agent = MagicMock(spec=Agent)
    agent.id = "agent-1"
    agent.owner = "owner-1"
    agent.team_id = "team-1"
    agent.fee_percentage = Decimal("0")
    agent.model = "gpt-4"

    mock_user_account = MagicMock(spec=CreditAccountTable)
    mock_user_account.id = "acc-user"
    mock_user_account.credits = Decimal("10.0")
    mock_user_account.free_credits = Decimal("0")
    mock_user_account.reward_credits = Decimal("0")

    mock_income_account = MagicMock(spec=CreditAccountTable)
    mock_income_account.id = "acc-income"

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    def side_effect_refresh(instance):
        instance.created_at = datetime.now()

    mock_session.refresh.side_effect = side_effect_refresh

    with (
        patch("intentkit.config.config.config.payment_enabled", True),
        patch(
            "intentkit.models.credit.CreditEvent.check_upstream_tx_id_exists",
            new_callable=AsyncMock,
        ),
        patch(
            "intentkit.models.credit.CreditAccount.expense_in_session",
            new_callable=AsyncMock,
            return_value=(mock_user_account, {CreditType.PERMANENT: base_llm_amount}),
        ),
        patch(
            "intentkit.models.app_setting.AppSetting.payment", new_callable=AsyncMock
        ) as mock_payment,
        patch(
            "intentkit.models.credit.CreditAccount.income_in_session",
            new_callable=AsyncMock,
            return_value=mock_income_account,
        ),
        patch(
            "intentkit.models.agent_data.AgentData.get",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "intentkit.core.credit.expense.accumulate_hourly_base_llm_amount",
            new_callable=AsyncMock,
        ),
    ):
        mock_payment.return_value.fee_platform_percentage = Decimal("20.0")

        result = await expense_summarize(
            mock_session,
            team_id=team_id,
            message_id=message_id,
            start_message_id=start_message_id,
            base_llm_amount=base_llm_amount,
            agent=agent,
            user_id="user-1",
        )

    assert result.event_type == "memory"
    added_objects = [call.args[0] for call in mock_session.add.call_args_list]
    transactions = [obj for obj in added_objects if hasattr(obj, "tx_type")]
    assert len(transactions) > 0


@pytest.mark.asyncio
async def test_expense_media_creates_event_and_transactions():
    team_id = "team-1"
    upstream_tx_id = "tx-avatar-1"
    base_original_amount = Decimal("5.0000")

    mock_team_account = MagicMock(spec=CreditAccountTable)
    mock_team_account.id = "acc-team"
    mock_team_account.credits = Decimal("100.0")
    mock_team_account.free_credits = Decimal("0")
    mock_team_account.reward_credits = Decimal("0")

    mock_income_account = MagicMock(spec=CreditAccountTable)
    mock_income_account.id = "acc-income"

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    def side_effect_refresh(instance):
        instance.created_at = datetime.now()

    mock_session.refresh.side_effect = side_effect_refresh

    with (
        patch("intentkit.config.config.config.payment_enabled", True),
        patch(
            "intentkit.models.credit.CreditEvent.check_upstream_tx_id_exists",
            new_callable=AsyncMock,
        ) as mock_idempotency,
        patch(
            "intentkit.models.credit.CreditAccount.expense_in_session",
            new_callable=AsyncMock,
            return_value=(
                mock_team_account,
                {CreditType.PERMANENT: Decimal("10.0000")},
            ),
        ) as mock_expense,
        patch(
            "intentkit.models.credit.CreditAccount.income_in_session",
            new_callable=AsyncMock,
            return_value=mock_income_account,
        ) as mock_income,
        patch(
            "intentkit.models.app_setting.AppSetting.payment", new_callable=AsyncMock
        ) as mock_payment,
    ):
        mock_payment.return_value.fee_platform_percentage = Decimal("100")

        result = await expense_media(
            mock_session,
            team_id=team_id,
            user_id="user-1",
            upstream_tx_id=upstream_tx_id,
            base_original_amount=base_original_amount,
        )

    mock_idempotency.assert_awaited_once()
    assert result.event_type == EventType.MEDIA.value
    assert result.upstream_type == UpstreamType.API.value
    assert result.agent_id is None
    assert result.skill_name is None
    assert result.message_id is None
    assert result.total_amount == Decimal("10.0000")
    assert result.base_amount == Decimal("5.0000")
    assert result.fee_platform_amount == Decimal("5.0000")
    assert result.fee_agent_amount == Decimal("0")

    # Expense called once for the team debit
    mock_expense.assert_called_once()
    # Income called twice: platform_media + platform_fee (no agent)
    assert mock_income.await_count == 2

    added_objects = [call.args[0] for call in mock_session.add.call_args_list]
    transactions = [obj for obj in added_objects if hasattr(obj, "tx_type")]
    tx_types = {tx.tx_type for tx in transactions}
    # Expect: PAY (team debit), RECEIVE_BASE_MEDIA (platform_media),
    # RECEIVE_FEE_PLATFORM (platform_fee)
    assert TransactionType.PAY in tx_types
    assert TransactionType.RECEIVE_BASE_MEDIA in tx_types
    assert TransactionType.RECEIVE_FEE_PLATFORM in tx_types


@pytest.mark.asyncio
async def test_expense_media_free_when_payment_disabled():
    """When payment_enabled=False, discount covers the base so total is zero
    and no account movements happen, but the event is still recorded."""
    team_id = "team-1"
    upstream_tx_id = "tx-avatar-2"
    base_original_amount = Decimal("5.0000")

    mock_team_account = MagicMock(spec=CreditAccountTable)
    mock_team_account.id = "acc-team"
    mock_team_account.credits = Decimal("0")
    mock_team_account.free_credits = Decimal("0")
    mock_team_account.reward_credits = Decimal("0")

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    def side_effect_refresh(instance):
        instance.created_at = datetime.now()

    mock_session.refresh.side_effect = side_effect_refresh

    with (
        patch("intentkit.config.config.config.payment_enabled", False),
        patch(
            "intentkit.models.credit.CreditEvent.check_upstream_tx_id_exists",
            new_callable=AsyncMock,
        ),
        patch(
            "intentkit.models.credit.CreditAccount.get_or_create_in_session",
            new_callable=AsyncMock,
            return_value=mock_team_account,
        ),
        patch(
            "intentkit.models.credit.CreditAccount.expense_in_session",
            new_callable=AsyncMock,
        ) as mock_expense,
        patch(
            "intentkit.models.credit.CreditAccount.income_in_session",
            new_callable=AsyncMock,
        ) as mock_income,
        patch(
            "intentkit.models.app_setting.AppSetting.payment", new_callable=AsyncMock
        ) as mock_payment,
    ):
        mock_payment.return_value.fee_platform_percentage = Decimal("100")

        result = await expense_media(
            mock_session,
            team_id=team_id,
            user_id="user-1",
            upstream_tx_id=upstream_tx_id,
            base_original_amount=base_original_amount,
        )

    assert result.event_type == EventType.MEDIA.value
    assert result.total_amount == Decimal("0")
    assert result.base_amount == Decimal("0")
    assert result.base_discount_amount == Decimal("5.0000")
    assert result.fee_platform_amount == Decimal("0")

    # No money moves
    mock_expense.assert_not_called()
    mock_income.assert_not_called()
