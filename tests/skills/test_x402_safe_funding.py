import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.skills.x402.pay import X402Pay

INSUFFICIENT_BALANCE = 5
REQUIRED_AMOUNT = 10
SUFFICIENT_BALANCE = 25


@pytest.mark.asyncio
async def test_safe_funding_transfers_when_balance_insufficient():
    skill = X402Pay()
    mock_agent = MagicMock()
    mock_agent.wallet_provider = "safe"
    mock_agent.id = "agent-id"
    mock_agent.network_id = "base-mainnet"

    mock_context = MagicMock()
    mock_context.agent = mock_agent

    privy_wallet_data = {
        "privy_wallet_id": "wallet-id",
        "privy_wallet_address": "0x1111111111111111111111111111111111111111",
        "smart_wallet_address": "0x2222222222222222222222222222222222222222",
        "network_id": "base-mainnet",
    }
    agent_data = MagicMock()
    agent_data.privy_wallet_data = json.dumps(privy_wallet_data)

    with (
        patch(
            "intentkit.skills.base.IntentKitSkill.get_context",
            return_value=mock_context,
        ),
        patch(
            "intentkit.models.agent_data.AgentData.get",
            new=AsyncMock(return_value=agent_data),
        ),
        patch.object(skill, "_resolve_rpc_url", return_value="https://rpc.example"),
        patch.object(
            skill,
            "_get_erc20_balance",
            new=AsyncMock(return_value=INSUFFICIENT_BALANCE),
        ),
        patch(
            "intentkit.skills.x402.base.transfer_erc20_gasless",
            new=AsyncMock(return_value="0xhash"),
        ) as mock_transfer,
    ):
        await skill._ensure_safe_funding(
            amount=REQUIRED_AMOUNT,
            token_address="0x3333333333333333333333333333333333333333",
            max_value=REQUIRED_AMOUNT,
        )

    mock_transfer.assert_awaited_once()
    call_kwargs = mock_transfer.call_args.kwargs
    assert (
        call_kwargs["amount"] == REQUIRED_AMOUNT - INSUFFICIENT_BALANCE
    )  # required - current_balance
    assert call_kwargs["to"] == privy_wallet_data["privy_wallet_address"]


@pytest.mark.asyncio
async def test_safe_funding_skips_when_balance_sufficient():
    skill = X402Pay()
    mock_agent = MagicMock()
    mock_agent.wallet_provider = "safe"
    mock_agent.id = "agent-id"
    mock_agent.network_id = "base-mainnet"

    mock_context = MagicMock()
    mock_context.agent = mock_agent

    privy_wallet_data = {
        "privy_wallet_id": "wallet-id",
        "privy_wallet_address": "0x1111111111111111111111111111111111111111",
        "smart_wallet_address": "0x2222222222222222222222222222222222222222",
        "network_id": "base-mainnet",
    }
    agent_data = MagicMock()
    agent_data.privy_wallet_data = json.dumps(privy_wallet_data)

    with (
        patch(
            "intentkit.skills.base.IntentKitSkill.get_context",
            return_value=mock_context,
        ),
        patch(
            "intentkit.models.agent_data.AgentData.get",
            new=AsyncMock(return_value=agent_data),
        ),
        patch.object(skill, "_resolve_rpc_url", return_value="https://rpc.example"),
        patch.object(
            skill,
            "_get_erc20_balance",
            new=AsyncMock(return_value=SUFFICIENT_BALANCE),
        ),
        patch(
            "intentkit.skills.x402.base.transfer_erc20_gasless",
            new=AsyncMock(return_value="0xhash"),
        ) as mock_transfer,
    ):
        await skill._ensure_safe_funding(
            amount=REQUIRED_AMOUNT,
            token_address="0x3333333333333333333333333333333333333333",
            max_value=REQUIRED_AMOUNT,
        )

    mock_transfer.assert_not_called()
