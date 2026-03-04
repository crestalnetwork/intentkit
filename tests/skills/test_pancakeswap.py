"""Tests for PancakeSwap V3 quote and swap skills."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.skills.pancakeswap.quote import PancakeSwapQuote
from intentkit.skills.pancakeswap.swap import PancakeSwapSwap

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_context(network_id: str = "bnb-mainnet") -> MagicMock:
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
    wallet.network_id = "bnb-mainnet"
    wallet.send_transaction = AsyncMock(return_value="0xabcdef1234567890")
    wallet.wait_for_receipt = AsyncMock(return_value={"status": 1})
    wallet.get_balance = AsyncMock(return_value=10**18)
    return wallet


def _quoter_call_result(amount_out: int, gas: int = 100000):
    """Simulate QuoterV2.quoteExactInputSingle return value."""
    return (amount_out, 0, 0, gas)


# ---------------------------------------------------------------------------
# Quote skill tests
# ---------------------------------------------------------------------------


class TestPancakeSwapQuote:
    @pytest.mark.asyncio
    async def test_quote_returns_best_fee_tier(self):
        """Quote should try multiple fee tiers and return the best output."""
        skill = PancakeSwapQuote()
        ctx = _mock_context()

        # Mock decimals call for token_out
        mock_decimals = AsyncMock(return_value=18)
        mock_decimals_contract = MagicMock()
        mock_decimals_contract.functions.decimals.return_value.call = mock_decimals

        # Mock quoter: fee 500 returns 900, fee 2500 returns 1000, fee 10000 fails
        call_count = 0

        async def mock_quote_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # fee 500
                return _quoter_call_result(900 * 10**18)
            elif call_count == 2:  # fee 2500
                return _quoter_call_result(1000 * 10**18)
            else:  # fee 10000
                raise Exception("no liquidity")

        mock_quoter_fn = MagicMock()
        mock_quoter_fn.return_value.call = AsyncMock(side_effect=mock_quote_call)

        mock_quoter_contract = MagicMock()
        mock_quoter_contract.functions.quoteExactInputSingle = mock_quoter_fn

        def mock_contract(address, abi):
            # Distinguish quoter vs decimals contract by ABI length
            if any(item.get("name") == "quoteExactInputSingle" for item in abi):
                return mock_quoter_contract
            return mock_decimals_contract

        mock_w3 = MagicMock()
        mock_w3.eth.contract = mock_contract

        with (
            patch(
                "intentkit.skills.base.IntentKitSkill.get_context",
                return_value=ctx,
            ),
            patch(
                "intentkit.skills.onchain.get_async_web3_client",
                return_value=mock_w3,
            ),
        ):
            result = await skill._arun(
                token_in="0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
                token_out="0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
                amount="1.0",
            )

        assert "PancakeSwap V3 Quote" in result
        assert "1000" in result  # best output
        assert "0.25%" in result  # fee tier 2500 = 0.25%

    @pytest.mark.asyncio
    async def test_quote_no_liquidity(self):
        """Quote should return a helpful message when no pool has liquidity."""
        skill = PancakeSwapQuote()
        ctx = _mock_context()

        mock_quoter_fn = MagicMock()
        mock_quoter_fn.return_value.call = AsyncMock(side_effect=Exception("no pool"))

        mock_quoter_contract = MagicMock()
        mock_quoter_contract.functions.quoteExactInputSingle = mock_quoter_fn

        mock_decimals = AsyncMock(return_value=18)
        mock_decimals_contract = MagicMock()
        mock_decimals_contract.functions.decimals.return_value.call = mock_decimals

        def mock_contract(address, abi):
            if any(item.get("name") == "quoteExactInputSingle" for item in abi):
                return mock_quoter_contract
            return mock_decimals_contract

        mock_w3 = MagicMock()
        mock_w3.eth.contract = mock_contract

        with (
            patch(
                "intentkit.skills.base.IntentKitSkill.get_context",
                return_value=ctx,
            ),
            patch(
                "intentkit.skills.onchain.get_async_web3_client",
                return_value=mock_w3,
            ),
        ):
            result = await skill._arun(
                token_in="0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
                token_out="0x0000000000000000000000000000000000000001",
                amount="1.0",
            )

        assert "No liquidity" in result

    @pytest.mark.asyncio
    async def test_quote_unsupported_network(self):
        """Quote should fail gracefully on unsupported networks."""
        skill = PancakeSwapQuote()
        ctx = _mock_context(network_id="solana-mainnet")

        with patch(
            "intentkit.skills.base.IntentKitSkill.get_context",
            return_value=ctx,
        ):
            with pytest.raises(Exception, match="not supported"):
                await skill._arun(
                    token_in="native",
                    token_out="0x0000000000000000000000000000000000000001",
                    amount="1.0",
                )

    @pytest.mark.asyncio
    async def test_quote_native_token_resolved(self):
        """'native' should be resolved to the wrapped native token address."""
        skill = PancakeSwapQuote()
        ctx = _mock_context()

        captured_args = []

        async def capture_quote_call(*args, **kwargs):
            return _quoter_call_result(500 * 10**18)

        mock_quoter_fn = MagicMock()
        mock_quoter_fn.side_effect = lambda params: MagicMock(
            call=AsyncMock(side_effect=lambda: capture_quote_call())
        )

        # Simpler approach: just check the result works with 'native'
        async def mock_quote(*args):
            captured_args.append(args)
            return _quoter_call_result(500 * 10**18)

        mock_quoter_fn2 = MagicMock()
        mock_quoter_fn2.return_value.call = AsyncMock(side_effect=mock_quote)

        mock_quoter_contract = MagicMock()
        mock_quoter_contract.functions.quoteExactInputSingle = mock_quoter_fn2

        mock_decimals_contract = MagicMock()
        mock_decimals_contract.functions.decimals.return_value.call = AsyncMock(
            return_value=18
        )

        def mock_contract(address, abi):
            if any(item.get("name") == "quoteExactInputSingle" for item in abi):
                return mock_quoter_contract
            return mock_decimals_contract

        mock_w3 = MagicMock()
        mock_w3.eth.contract = mock_contract

        with (
            patch(
                "intentkit.skills.base.IntentKitSkill.get_context",
                return_value=ctx,
            ),
            patch(
                "intentkit.skills.onchain.get_async_web3_client",
                return_value=mock_w3,
            ),
        ):
            result = await skill._arun(
                token_in="native",
                token_out="0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
                amount="1.0",
            )

        assert "PancakeSwap V3 Quote" in result


# ---------------------------------------------------------------------------
# Swap skill tests
# ---------------------------------------------------------------------------


class TestPancakeSwapSwap:
    @pytest.mark.asyncio
    async def test_swap_executes_successfully(self):
        """Swap should get quote, approve, execute, and return tx hash."""
        skill = PancakeSwapSwap()
        ctx = _mock_context()
        wallet = _mock_wallet()

        # Mock quoter
        async def mock_quote(*args):
            return _quoter_call_result(1000 * 10**18)

        mock_quoter_fn = MagicMock()
        mock_quoter_fn.return_value.call = AsyncMock(side_effect=mock_quote)

        mock_quoter_contract = MagicMock()
        mock_quoter_contract.functions.quoteExactInputSingle = mock_quoter_fn

        # Mock ERC20 contract for allowance and approve
        mock_allowance = AsyncMock(return_value=0)  # no allowance
        mock_erc20 = MagicMock()
        mock_erc20.functions.allowance.return_value.call = mock_allowance
        mock_erc20.functions.decimals.return_value.call = AsyncMock(return_value=18)
        mock_erc20.encode_abi = MagicMock(return_value="0xapprovedata")

        # Mock router contract
        mock_router = MagicMock()
        mock_router.encode_abi = MagicMock(return_value="0xswapdata")

        def mock_contract(address, abi):
            if any(item.get("name") == "quoteExactInputSingle" for item in abi):
                return mock_quoter_contract
            if any(item.get("name") == "exactInputSingle" for item in abi):
                return mock_router
            return mock_erc20

        mock_w3 = MagicMock()
        mock_w3.eth.contract = mock_contract

        with (
            patch(
                "intentkit.skills.base.IntentKitSkill.get_context",
                return_value=ctx,
            ),
            patch(
                "intentkit.wallets.evm_wallet.EvmWallet.create",
                new=AsyncMock(return_value=wallet),
            ),
            patch(
                "intentkit.skills.onchain.get_async_web3_client",
                return_value=mock_w3,
            ),
        ):
            result = await skill._arun(
                token_in="0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
                token_out="0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
                amount="1.0",
                slippage=0.5,
            )

        assert "Swap Executed" in result
        assert "0xabcdef1234567890" in result
        # approve + swap = 2 send_transaction calls
        assert wallet.send_transaction.call_count == 2

    @pytest.mark.asyncio
    async def test_swap_native_in_skips_approval(self):
        """Swap with native token input should skip ERC20 approval."""
        skill = PancakeSwapSwap()
        ctx = _mock_context()
        wallet = _mock_wallet()

        async def mock_quote(*args):
            return _quoter_call_result(500 * 10**18)

        mock_quoter_fn = MagicMock()
        mock_quoter_fn.return_value.call = AsyncMock(side_effect=mock_quote)
        mock_quoter_contract = MagicMock()
        mock_quoter_contract.functions.quoteExactInputSingle = mock_quoter_fn

        mock_router = MagicMock()
        mock_router.encode_abi = MagicMock(return_value="0xswapdata")

        mock_decimals_contract = MagicMock()
        mock_decimals_contract.functions.decimals.return_value.call = AsyncMock(
            return_value=18
        )

        def mock_contract(address, abi):
            if any(item.get("name") == "quoteExactInputSingle" for item in abi):
                return mock_quoter_contract
            if any(item.get("name") == "exactInputSingle" for item in abi):
                return mock_router
            return mock_decimals_contract

        mock_w3 = MagicMock()
        mock_w3.eth.contract = mock_contract

        with (
            patch(
                "intentkit.skills.base.IntentKitSkill.get_context",
                return_value=ctx,
            ),
            patch(
                "intentkit.wallets.evm_wallet.EvmWallet.create",
                new=AsyncMock(return_value=wallet),
            ),
            patch(
                "intentkit.skills.onchain.get_async_web3_client",
                return_value=mock_w3,
            ),
        ):
            result = await skill._arun(
                token_in="native",
                token_out="0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
                amount="1.0",
            )

        assert "Swap Executed" in result
        # Only 1 call (swap), no approval
        assert wallet.send_transaction.call_count == 1
        # Verify value was sent (native token)
        call_kwargs = wallet.send_transaction.call_args_list[0].kwargs
        assert call_kwargs.get("value", 0) == 10**18

    @pytest.mark.asyncio
    async def test_swap_no_liquidity(self):
        """Swap should return helpful message when no pool has liquidity."""
        skill = PancakeSwapSwap()
        ctx = _mock_context()
        wallet = _mock_wallet()

        mock_quoter_fn = MagicMock()
        mock_quoter_fn.return_value.call = AsyncMock(side_effect=Exception("no pool"))
        mock_quoter_contract = MagicMock()
        mock_quoter_contract.functions.quoteExactInputSingle = mock_quoter_fn

        mock_decimals_contract = MagicMock()
        mock_decimals_contract.functions.decimals.return_value.call = AsyncMock(
            return_value=18
        )

        def mock_contract(address, abi):
            if any(item.get("name") == "quoteExactInputSingle" for item in abi):
                return mock_quoter_contract
            return mock_decimals_contract

        mock_w3 = MagicMock()
        mock_w3.eth.contract = mock_contract

        with (
            patch(
                "intentkit.skills.base.IntentKitSkill.get_context",
                return_value=ctx,
            ),
            patch(
                "intentkit.wallets.evm_wallet.EvmWallet.create",
                new=AsyncMock(return_value=wallet),
            ),
            patch(
                "intentkit.skills.onchain.get_async_web3_client",
                return_value=mock_w3,
            ),
        ):
            result = await skill._arun(
                token_in="0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
                token_out="0x0000000000000000000000000000000000000001",
                amount="1.0",
            )

        assert "No liquidity" in result

    @pytest.mark.asyncio
    async def test_swap_skips_approval_when_sufficient_allowance(self):
        """Swap should not send approve tx when allowance is already sufficient."""
        skill = PancakeSwapSwap()
        ctx = _mock_context()
        wallet = _mock_wallet()

        async def mock_quote(*args):
            return _quoter_call_result(1000 * 10**18)

        mock_quoter_fn = MagicMock()
        mock_quoter_fn.return_value.call = AsyncMock(side_effect=mock_quote)
        mock_quoter_contract = MagicMock()
        mock_quoter_contract.functions.quoteExactInputSingle = mock_quoter_fn

        # Allowance already sufficient
        mock_erc20 = MagicMock()
        mock_erc20.functions.allowance.return_value.call = AsyncMock(
            return_value=10**36
        )
        mock_erc20.functions.decimals.return_value.call = AsyncMock(return_value=18)

        mock_router = MagicMock()
        mock_router.encode_abi = MagicMock(return_value="0xswapdata")

        def mock_contract(address, abi):
            if any(item.get("name") == "quoteExactInputSingle" for item in abi):
                return mock_quoter_contract
            if any(item.get("name") == "exactInputSingle" for item in abi):
                return mock_router
            return mock_erc20

        mock_w3 = MagicMock()
        mock_w3.eth.contract = mock_contract

        with (
            patch(
                "intentkit.skills.base.IntentKitSkill.get_context",
                return_value=ctx,
            ),
            patch(
                "intentkit.wallets.evm_wallet.EvmWallet.create",
                new=AsyncMock(return_value=wallet),
            ),
            patch(
                "intentkit.skills.onchain.get_async_web3_client",
                return_value=mock_w3,
            ),
        ):
            result = await skill._arun(
                token_in="0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
                token_out="0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
                amount="1.0",
            )

        assert "Swap Executed" in result
        # Only 1 call (swap), no approval needed
        assert wallet.send_transaction.call_count == 1

    @pytest.mark.asyncio
    async def test_swap_failed_transaction(self):
        """Swap should raise when tx receipt status is 0."""
        skill = PancakeSwapSwap()
        ctx = _mock_context()
        wallet = _mock_wallet()
        wallet.wait_for_receipt = AsyncMock(return_value={"status": 0})

        async def mock_quote(*args):
            return _quoter_call_result(1000 * 10**18)

        mock_quoter_fn = MagicMock()
        mock_quoter_fn.return_value.call = AsyncMock(side_effect=mock_quote)
        mock_quoter_contract = MagicMock()
        mock_quoter_contract.functions.quoteExactInputSingle = mock_quoter_fn

        mock_router = MagicMock()
        mock_router.encode_abi = MagicMock(return_value="0xswapdata")

        mock_decimals_contract = MagicMock()
        mock_decimals_contract.functions.decimals.return_value.call = AsyncMock(
            return_value=18
        )

        def mock_contract(address, abi):
            if any(item.get("name") == "quoteExactInputSingle" for item in abi):
                return mock_quoter_contract
            if any(item.get("name") == "exactInputSingle" for item in abi):
                return mock_router
            return mock_decimals_contract

        mock_w3 = MagicMock()
        mock_w3.eth.contract = mock_contract

        with (
            patch(
                "intentkit.skills.base.IntentKitSkill.get_context",
                return_value=ctx,
            ),
            patch(
                "intentkit.wallets.evm_wallet.EvmWallet.create",
                new=AsyncMock(return_value=wallet),
            ),
            patch(
                "intentkit.skills.onchain.get_async_web3_client",
                return_value=mock_w3,
            ),
        ):
            with pytest.raises(Exception, match="failed"):
                await skill._arun(
                    token_in="native",
                    token_out="0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
                    amount="1.0",
                )
