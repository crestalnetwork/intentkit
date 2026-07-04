import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from web3.exceptions import TimeExhausted, Web3RPCError

from intentkit.models.wallet import TeamWallet
from intentkit.tools.x402.pay import X402Pay

INSUFFICIENT_BALANCE = 5
REQUIRED_AMOUNT = 10
SUFFICIENT_BALANCE = 25

PRIVY_WALLET_DATA = {
    "privy_wallet_id": "wallet-id",
    "privy_wallet_address": "0x1111111111111111111111111111111111111111",
    "smart_wallet_address": "0x2222222222222222222222222222222222222222",
    "network_id": "base-mainnet",
}


def _safe_wallet() -> TeamWallet:
    """Build a Safe team wallet carrying the privy payload, bypassing the DB."""
    now = datetime.now()
    return TeamWallet(
        id="wallet-1",
        team_id="team-1",
        name="safe",
        wallet_provider="safe",
        network_id="base-mainnet",
        evm_wallet_address=PRIVY_WALLET_DATA["smart_wallet_address"],
        wallet_data=json.dumps(PRIVY_WALLET_DATA),
        created_by="user-1",
        created_at=now,
        updated_at=now,
    )


def _safe_agent_context() -> MagicMock:
    """Build a tool context whose agent is bound to the safe team wallet."""
    mock_agent = MagicMock()
    mock_agent.id = "agent-id"
    mock_agent.team_id = "team-1"
    mock_agent.wallet_id = "wallet-1"
    mock_agent.network_id = "base-mainnet"

    mock_context = MagicMock()
    mock_context.agent = mock_agent
    return mock_context


@pytest.mark.asyncio
async def test_safe_funding_transfers_when_balance_insufficient():
    tool = X402Pay()
    mock_context = _safe_agent_context()

    with (
        patch(
            "intentkit.tools.base.IntentKitTool.get_context",
            return_value=mock_context,
        ),
        patch(
            "intentkit.models.wallet.TeamWallet.get",
            new=AsyncMock(return_value=_safe_wallet()),
        ),
        patch.object(tool, "_resolve_rpc_url", return_value="https://rpc.example"),
        patch.object(
            tool,
            "_get_erc20_balance",
            new=AsyncMock(return_value=INSUFFICIENT_BALANCE),
        ),
        patch(
            "intentkit.tools.x402.base.transfer_erc20_gasless",
            new=AsyncMock(return_value="0xhash"),
        ) as mock_transfer,
    ):
        await tool.ensure_safe_funding(
            amount=REQUIRED_AMOUNT,
            token_address="0x3333333333333333333333333333333333333333",
            max_value=REQUIRED_AMOUNT,
        )

    mock_transfer.assert_awaited_once()
    call_kwargs = mock_transfer.call_args.kwargs
    assert (
        call_kwargs["amount"] == REQUIRED_AMOUNT - INSUFFICIENT_BALANCE
    )  # required - current_balance
    assert call_kwargs["to"] == PRIVY_WALLET_DATA["privy_wallet_address"]


@pytest.mark.asyncio
async def test_safe_funding_skips_when_balance_sufficient():
    tool = X402Pay()
    mock_context = _safe_agent_context()

    with (
        patch(
            "intentkit.tools.base.IntentKitTool.get_context",
            return_value=mock_context,
        ),
        patch(
            "intentkit.models.wallet.TeamWallet.get",
            new=AsyncMock(return_value=_safe_wallet()),
        ),
        patch.object(tool, "_resolve_rpc_url", return_value="https://rpc.example"),
        patch.object(
            tool,
            "_get_erc20_balance",
            new=AsyncMock(return_value=SUFFICIENT_BALANCE),
        ),
        patch(
            "intentkit.tools.x402.base.transfer_erc20_gasless",
            new=AsyncMock(return_value="0xhash"),
        ) as mock_transfer,
    ):
        await tool.ensure_safe_funding(
            amount=REQUIRED_AMOUNT,
            token_address="0x3333333333333333333333333333333333333333",
            max_value=REQUIRED_AMOUNT,
        )

    mock_transfer.assert_not_called()


@pytest.mark.asyncio
async def test_x402_pay_returns_tool_error_when_prefund_fails():
    tool = X402Pay()

    with patch.object(
        tool,
        "_prefund_safe_wallet",
        new=AsyncMock(side_effect=RuntimeError("insufficient gas for transfer")),
    ):
        result = await tool.arun(
            {
                "method": "GET",
                "url": "https://example.com/pay",
                "max_value": 1,
            }
        )

    assert result.startswith("tool error:")
    assert "insufficient gas for transfer" in result


@pytest.mark.asyncio
async def test_x402_pay_returns_timeout_tool_error_when_prefund_receipt_times_out():
    tool = X402Pay()

    with patch.object(
        tool,
        "_prefund_safe_wallet",
        new=AsyncMock(
            side_effect=TimeExhausted(
                "Transaction HexBytes('0xabc') is not in the chain after 120 seconds"
            )
        ),
    ):
        result = await tool.arun(
            {
                "method": "GET",
                "url": "https://example.com/pay",
                "max_value": 1,
            }
        )

    assert result.startswith("tool error:")
    assert "not confirmed before timeout" in result


@pytest.mark.asyncio
async def test_x402_pay_returns_gas_tool_error_when_prefund_rpc_has_insufficient_funds():
    tool = X402Pay()

    with (
        patch.object(
            tool,
            "_prefund_safe_wallet",
            new=AsyncMock(
                side_effect=Web3RPCError(
                    "insufficient funds for gas * price + value: have 177004000000000 "
                    "want 55000000000000000"
                )
            ),
        ),
        patch(
            "intentkit.tools.x402.base.send_alert",
        ) as mock_send_alert,
    ):
        result = await tool.arun(
            {
                "method": "GET",
                "url": "https://example.com/pay",
                "max_value": 1,
            }
        )

    assert result.startswith("tool error:")
    assert "temporarily unavailable" in result
    mock_send_alert.assert_called_once()
    assert "paymaster gas shortage" in mock_send_alert.call_args.kwargs["message"]
