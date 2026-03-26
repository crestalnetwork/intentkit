"""Tests for Aave V3 lending protocol skills."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools.base import ToolException

from intentkit.skills.aave_v3.constants import MAX_UINT256
from intentkit.skills.aave_v3.supply import AaveV3Supply
from intentkit.skills.aave_v3.utils import (
    convert_amount,
    ensure_allowance,
    format_amount,
    format_base_currency,
    format_health_factor,
    format_ray,
)
from intentkit.skills.aave_v3.withdraw import AaveV3Withdraw

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_context(network_id: str = "base-mainnet") -> MagicMock:
    mock_agent = MagicMock()
    mock_agent.network_id = network_id
    mock_agent.id = "test-agent"
    mock_agent.wallet_provider = "cdp"
    ctx = MagicMock()
    ctx.agent = mock_agent
    return ctx


def _mock_wallet(
    address: str = "0x1111111111111111111111111111111111111111",
) -> MagicMock:
    wallet = MagicMock()
    wallet.address = address
    wallet.network_id = "base-mainnet"
    wallet.send_transaction = AsyncMock(return_value="0xabcdef1234567890")
    wallet.wait_for_receipt = AsyncMock(return_value={"status": 1})
    return wallet


def _mock_w3_with_decimals(decimals: int = 18) -> MagicMock:
    mock_decimals = AsyncMock(return_value=decimals)
    mock_contract = MagicMock()
    mock_contract.functions.decimals.return_value.call = mock_decimals
    mock_contract.functions.symbol.return_value.call = AsyncMock(return_value="USDC")
    mock_contract.functions.allowance.return_value.call = AsyncMock(return_value=0)
    mock_contract.encode_abi = MagicMock(return_value="0xencodeddata")

    mock_w3 = MagicMock()
    mock_w3.eth.contract = MagicMock(return_value=mock_contract)
    return mock_w3


# ---------------------------------------------------------------------------
# Utils: pure formatting functions
# ---------------------------------------------------------------------------


class TestConvertAmount:
    def test_whole_units(self):
        assert convert_amount("100", 6) == 100_000_000

    def test_fractional(self):
        assert convert_amount("1.5", 18) == 1_500_000_000_000_000_000

    def test_zero_raises(self):
        with pytest.raises(ToolException, match="positive"):
            convert_amount("0", 18)

    def test_negative_raises(self):
        with pytest.raises(ToolException, match="positive"):
            convert_amount("-1", 18)


class TestFormatAmount:
    def test_round_trip(self):
        raw = convert_amount("123.456", 6)
        assert format_amount(raw, 6) == "123.456"

    def test_zero(self):
        assert format_amount(0, 18) == "0"


class TestFormatHealthFactor:
    def test_normal_value(self):
        # 1.5 health factor = 1.5 * 10^18
        raw = 1_500_000_000_000_000_000
        assert format_health_factor(raw) == "1.5000"

    def test_max_uint256(self):
        result = format_health_factor(MAX_UINT256)
        assert "no borrows" in result

    def test_low_health(self):
        raw = 1_050_000_000_000_000_000  # 1.05
        assert format_health_factor(raw) == "1.0500"


class TestFormatRay:
    def test_typical_apy(self):
        # 3% APY = 0.03 * 10^27
        raw = 30_000_000_000_000_000_000_000_000
        assert format_ray(raw) == "3.00%"

    def test_zero(self):
        assert format_ray(0) == "0.00%"


class TestFormatBaseCurrency:
    def test_typical_value(self):
        # $1000.50 = 1000.50 * 10^8
        raw = 100_050_000_000
        assert format_base_currency(raw) == "$1,000.50"

    def test_zero(self):
        assert format_base_currency(0) == "$0.00"


# ---------------------------------------------------------------------------
# Utils: ensure_allowance with USDT reset-to-zero
# ---------------------------------------------------------------------------


class TestEnsureAllowance:
    @pytest.mark.asyncio
    async def test_skips_when_sufficient(self):
        wallet = _mock_wallet()
        mock_contract = MagicMock()
        mock_contract.functions.allowance.return_value.call = AsyncMock(
            return_value=1000
        )
        mock_w3 = MagicMock()
        mock_w3.eth.contract = MagicMock(return_value=mock_contract)

        await ensure_allowance(mock_w3, wallet, "0xToken", "0xSpender", 500)

        wallet.send_transaction.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_approves_when_zero_allowance(self):
        wallet = _mock_wallet()
        mock_contract = MagicMock()
        mock_contract.functions.allowance.return_value.call = AsyncMock(return_value=0)
        mock_contract.encode_abi = MagicMock(return_value="0xapprovedata")
        mock_w3 = MagicMock()
        mock_w3.eth.contract = MagicMock(return_value=mock_contract)

        await ensure_allowance(mock_w3, wallet, "0xToken", "0xSpender", 1000)

        # One approve tx, no reset-to-zero
        assert wallet.send_transaction.await_count == 1

    @pytest.mark.asyncio
    async def test_resets_to_zero_for_usdt_style_tokens(self):
        """When current allowance > 0 but < needed, reset to 0 first (USDT pattern)."""
        wallet = _mock_wallet()
        mock_contract = MagicMock()
        mock_contract.functions.allowance.return_value.call = AsyncMock(return_value=50)
        mock_contract.encode_abi = MagicMock(return_value="0xdata")
        mock_w3 = MagicMock()
        mock_w3.eth.contract = MagicMock(return_value=mock_contract)

        await ensure_allowance(mock_w3, wallet, "0xToken", "0xSpender", 1000)

        # Two txs: reset to 0, then approve new amount
        assert wallet.send_transaction.await_count == 2
        assert wallet.wait_for_receipt.await_count == 2


# ---------------------------------------------------------------------------
# Supply skill
# ---------------------------------------------------------------------------


class TestAaveV3Supply:
    @pytest.mark.asyncio
    async def test_supply_success(self):
        skill = AaveV3Supply()
        ctx = _mock_context()
        wallet = _mock_wallet()
        mock_w3 = _mock_w3_with_decimals(6)

        with (
            patch(
                "intentkit.skills.base.IntentKitSkill.get_context",
                return_value=ctx,
            ),
            patch(
                "intentkit.skills.onchain.get_async_web3_client",
                return_value=mock_w3,
            ),
            patch(
                "intentkit.wallets.evm_wallet.EvmWallet.create",
                new=AsyncMock(return_value=wallet),
            ),
        ):
            result = await skill._arun(
                token_address="0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
                amount="100",
            )

        assert "Aave V3 Supply" in result
        assert "100" in result
        assert "0xabcdef" in result

    @pytest.mark.asyncio
    async def test_supply_unsupported_network(self):
        skill = AaveV3Supply()
        ctx = _mock_context(network_id="solana-mainnet")

        with (
            patch(
                "intentkit.skills.base.IntentKitSkill.get_context",
                return_value=ctx,
            ),
        ):
            with pytest.raises(ToolException, match="not supported"):
                await skill._arun(
                    token_address="0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
                    amount="100",
                )

    @pytest.mark.asyncio
    async def test_supply_failed_transaction(self):
        skill = AaveV3Supply()
        ctx = _mock_context()
        wallet = _mock_wallet()
        wallet.wait_for_receipt = AsyncMock(return_value={"status": 0})
        mock_w3 = _mock_w3_with_decimals(6)

        with (
            patch(
                "intentkit.skills.base.IntentKitSkill.get_context",
                return_value=ctx,
            ),
            patch(
                "intentkit.skills.onchain.get_async_web3_client",
                return_value=mock_w3,
            ),
            patch(
                "intentkit.wallets.evm_wallet.EvmWallet.create",
                new=AsyncMock(return_value=wallet),
            ),
        ):
            with pytest.raises(ToolException, match="failed"):
                await skill._arun(
                    token_address="0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
                    amount="100",
                )


# ---------------------------------------------------------------------------
# Withdraw skill
# ---------------------------------------------------------------------------


class TestAaveV3Withdraw:
    @pytest.mark.asyncio
    async def test_withdraw_max(self):
        skill = AaveV3Withdraw()
        ctx = _mock_context()
        wallet = _mock_wallet()
        mock_w3 = _mock_w3_with_decimals(18)

        with (
            patch(
                "intentkit.skills.base.IntentKitSkill.get_context",
                return_value=ctx,
            ),
            patch(
                "intentkit.skills.onchain.get_async_web3_client",
                return_value=mock_w3,
            ),
            patch(
                "intentkit.wallets.evm_wallet.EvmWallet.create",
                new=AsyncMock(return_value=wallet),
            ),
        ):
            result = await skill._arun(
                token_address="0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
                amount="max",
            )

        assert "Aave V3 Withdraw" in result
        assert "max" in result

    @pytest.mark.asyncio
    async def test_withdraw_specific_amount(self):
        skill = AaveV3Withdraw()
        ctx = _mock_context()
        wallet = _mock_wallet()
        mock_w3 = _mock_w3_with_decimals(6)

        with (
            patch(
                "intentkit.skills.base.IntentKitSkill.get_context",
                return_value=ctx,
            ),
            patch(
                "intentkit.skills.onchain.get_async_web3_client",
                return_value=mock_w3,
            ),
            patch(
                "intentkit.wallets.evm_wallet.EvmWallet.create",
                new=AsyncMock(return_value=wallet),
            ),
        ):
            result = await skill._arun(
                token_address="0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
                amount="50.5",
            )

        assert "Aave V3 Withdraw" in result
        assert "50.5" in result
        # Should not send approval tx for withdraw
        # 2 calls: decimals + symbol (via gather), then 1 send_transaction for withdraw
        assert wallet.send_transaction.await_count == 1
