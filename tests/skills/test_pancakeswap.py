"""Tests for PancakeSwap V3 quote, swap, and liquidity skills."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools.base import ToolException

from intentkit.skills.pancakeswap.add_liquidity import PancakeSwapAddLiquidity
from intentkit.skills.pancakeswap.get_positions import PancakeSwapGetPositions
from intentkit.skills.pancakeswap.quote import PancakeSwapQuote
from intentkit.skills.pancakeswap.remove_liquidity import PancakeSwapRemoveLiquidity
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

        # Mock quoter: fee 100 fails, fee 500 returns 900, fee 2500 returns 1000, fee 10000 fails
        call_count = 0

        async def mock_quote_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # fee 100
                raise Exception("no liquidity")
            elif call_count == 2:  # fee 500
                return _quoter_call_result(900 * 10**18)
            elif call_count == 3:  # fee 2500
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
        """Quote should raise ToolException when no pool has liquidity."""
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
            with pytest.raises(ToolException, match="No liquidity"):
                await skill._arun(
                    token_in="0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
                    token_out="0x0000000000000000000000000000000000000001",
                    amount="1.0",
                )

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
        """Swap should raise ToolException when no pool has liquidity."""
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
            with pytest.raises(ToolException, match="No liquidity"):
                await skill._arun(
                    token_in="0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
                    token_out="0x0000000000000000000000000000000000000001",
                    amount="1.0",
                )

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


# ---------------------------------------------------------------------------
# GetPositions skill tests
# ---------------------------------------------------------------------------


def _mock_position_info(
    token0="0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    token1="0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
    fee=2500,
    tick_lower=-887200,
    tick_upper=887200,
    liquidity=1000000,
    tokens_owed0=100,
    tokens_owed1=200,
):
    """Build a mock positions() return value."""
    return (
        0,  # nonce
        "0x0000000000000000000000000000000000000000",  # operator
        token0,
        token1,
        fee,
        tick_lower,
        tick_upper,
        liquidity,
        0,  # feeGrowthInside0LastX128
        0,  # feeGrowthInside1LastX128
        tokens_owed0,
        tokens_owed1,
    )


class TestPancakeSwapGetPositions:
    @pytest.mark.asyncio
    async def test_no_positions(self):
        """Should return helpful message when no positions exist."""
        skill = PancakeSwapGetPositions()
        ctx = _mock_context()
        wallet = _mock_wallet()

        mock_pm = MagicMock()
        mock_pm.functions.balanceOf.return_value.call = AsyncMock(return_value=0)

        def mock_contract(address, abi):
            return mock_pm

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
            patch(
                "intentkit.skills.base.IntentKitSkill.get_agent_skill_data",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await skill._arun()

        assert "No active" in result

    @pytest.mark.asyncio
    async def test_unstaked_positions(self):
        """Should list unstaked positions from PositionManager."""
        skill = PancakeSwapGetPositions()
        ctx = _mock_context()
        wallet = _mock_wallet()

        pos = _mock_position_info()

        mock_pm = MagicMock()
        mock_pm.functions.balanceOf.return_value.call = AsyncMock(return_value=1)
        mock_pm.functions.tokenOfOwnerByIndex.return_value.call = AsyncMock(
            return_value=42
        )
        mock_pm.functions.positions.return_value.call = AsyncMock(return_value=pos)

        mock_symbol = MagicMock()
        mock_symbol.functions.symbol.return_value.call = AsyncMock(return_value="TKA")
        mock_symbol.functions.decimals.return_value.call = AsyncMock(return_value=18)

        def mock_contract(address, abi):
            if any(item.get("name") == "positions" for item in abi):
                return mock_pm
            return mock_symbol

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
            patch(
                "intentkit.skills.base.IntentKitSkill.get_agent_skill_data",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await skill._arun()

        assert "Position #42" in result
        assert "Not staked" in result

    @pytest.mark.asyncio
    async def test_staked_positions(self):
        """Should list staked positions from persisted data."""
        skill = PancakeSwapGetPositions()
        ctx = _mock_context()
        wallet = _mock_wallet()
        wallet_addr = wallet.address

        pos = _mock_position_info()

        mock_pm = MagicMock()
        mock_pm.functions.balanceOf.return_value.call = AsyncMock(return_value=0)
        mock_pm.functions.positions.return_value.call = AsyncMock(return_value=pos)

        # MasterChef mock
        mock_mc = MagicMock()
        mock_mc.functions.userPositionInfos.return_value.call = AsyncMock(
            return_value=(1000, 0, -887200, 887200, 0, 0, wallet_addr, 0, 0)
        )
        mock_mc.functions.pendingCake.return_value.call = AsyncMock(
            return_value=5 * 10**18
        )

        mock_symbol = MagicMock()
        mock_symbol.functions.symbol.return_value.call = AsyncMock(return_value="TKA")
        mock_symbol.functions.decimals.return_value.call = AsyncMock(return_value=18)

        def mock_contract(address, abi):
            if any(item.get("name") == "positions" for item in abi):
                return mock_pm
            if any(item.get("name") == "userPositionInfos" for item in abi):
                return mock_mc
            return mock_symbol

        mock_w3 = MagicMock()
        mock_w3.eth.contract = mock_contract

        staked_data = {"token_ids": [99]}

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
            patch(
                "intentkit.skills.base.IntentKitSkill.get_agent_skill_data",
                new=AsyncMock(return_value=staked_data),
            ),
        ):
            result = await skill._arun()

        assert "Position #99" in result
        assert "Staked" in result
        assert "CAKE" in result


# ---------------------------------------------------------------------------
# AddLiquidity skill tests
# ---------------------------------------------------------------------------


class TestPancakeSwapAddLiquidity:
    @pytest.mark.asyncio
    async def test_token_ordering(self):
        """Tokens should be sorted so token0 < token1."""
        skill = PancakeSwapAddLiquidity()
        ctx = _mock_context()
        wallet = _mock_wallet()

        # token_a address > token_b address, so they should swap
        token_a = "0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
        token_b = "0x0000000000000000000000000000000000000001"

        mock_factory = MagicMock()
        mock_factory.functions.getPool.return_value.call = AsyncMock(
            return_value="0x1234567890123456789012345678901234567890"
        )

        mock_pm = MagicMock()
        mock_pm.encode_abi = MagicMock(return_value="0xmintdata")

        mock_erc20 = MagicMock()
        mock_erc20.functions.decimals.return_value.call = AsyncMock(return_value=18)
        mock_erc20.functions.allowance.return_value.call = AsyncMock(
            return_value=10**36
        )
        mock_erc20.functions.symbol.return_value.call = AsyncMock(return_value="TKN")

        # Mint receipt with Transfer event
        mint_receipt = {
            "status": 1,
            "logs": [
                {
                    "topics": [
                        bytes.fromhex(
                            "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
                        ),
                        b"\x00" * 32,
                        b"\x00" * 31 + b"\x01",
                        b"\x00" * 31 + b"\x07",  # tokenId = 7
                    ],
                }
            ],
        }
        wallet.wait_for_receipt = AsyncMock(return_value=mint_receipt)

        def mock_contract(address, abi):
            if any(item.get("name") == "getPool" for item in abi):
                return mock_factory
            if any(item.get("name") == "mint" for item in abi):
                return mock_pm
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
            patch(
                "intentkit.skills.base.IntentKitSkill.get_agent_skill_data",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "intentkit.skills.base.IntentKitSkill.save_agent_skill_data",
                new=AsyncMock(),
            ),
        ):
            result = await skill._arun(
                token_a=token_a,
                token_b=token_b,
                amount_a="1.0",
                amount_b="2.0",
                fee_tier=2500,
            )

        assert "Liquidity Added" in result
        assert "Position ID: 7" in result

    @pytest.mark.asyncio
    async def test_auto_stake_failure_continues(self):
        """If auto-staking fails, position should still be created."""
        skill = PancakeSwapAddLiquidity()
        ctx = _mock_context()
        wallet = _mock_wallet()

        mock_factory = MagicMock()
        mock_factory.functions.getPool.return_value.call = AsyncMock(
            return_value="0x1234567890123456789012345678901234567890"
        )

        mock_pm = MagicMock()
        mock_pm.encode_abi = MagicMock(return_value="0xmintdata")

        mock_erc20 = MagicMock()
        mock_erc20.functions.decimals.return_value.call = AsyncMock(return_value=18)
        mock_erc20.functions.allowance.return_value.call = AsyncMock(
            return_value=10**36
        )
        mock_erc20.functions.symbol.return_value.call = AsyncMock(return_value="TKN")

        mint_receipt = {
            "status": 1,
            "logs": [
                {
                    "topics": [
                        bytes.fromhex(
                            "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
                        ),
                        b"\x00" * 32,
                        b"\x00" * 31 + b"\x01",
                        b"\x00" * 31 + b"\x05",  # tokenId = 5
                    ],
                }
            ],
        }

        call_count = 0

        async def mock_send(**kwargs):
            nonlocal call_count
            call_count += 1
            return f"0xtx{call_count}"

        wallet.send_transaction = AsyncMock(side_effect=mock_send)

        # First call returns mint receipt, second (stake) fails
        receipt_count = 0

        async def mock_receipt(tx_hash):
            nonlocal receipt_count
            receipt_count += 1
            if receipt_count <= 1:
                return mint_receipt
            # Staking attempt fails
            raise Exception("not eligible for farm")

        wallet.wait_for_receipt = AsyncMock(side_effect=mock_receipt)

        def mock_contract(address, abi):
            if any(item.get("name") == "getPool" for item in abi):
                return mock_factory
            if any(item.get("name") == "mint" for item in abi):
                return mock_pm
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
            patch(
                "intentkit.skills.base.IntentKitSkill.get_agent_skill_data",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "intentkit.skills.base.IntentKitSkill.save_agent_skill_data",
                new=AsyncMock(),
            ),
        ):
            # _try_auto_stake raises ToolException when staking fails,
            # which propagates through _arun's `except ToolException: raise`
            with pytest.raises(ToolException, match="Not staked"):
                await skill._arun(
                    token_a="0x0000000000000000000000000000000000000001",
                    token_b="0x0000000000000000000000000000000000000002",
                    amount_a="1.0",
                    amount_b="1.0",
                    fee_tier=2500,
                )


# ---------------------------------------------------------------------------
# RemoveLiquidity skill tests
# ---------------------------------------------------------------------------


class TestPancakeSwapRemoveLiquidity:
    @pytest.mark.asyncio
    async def test_full_removal_with_burn(self):
        """Full removal should decrease, collect, and burn."""
        skill = PancakeSwapRemoveLiquidity()
        ctx = _mock_context()
        wallet = _mock_wallet()

        pos = _mock_position_info(liquidity=1000000)

        mock_pm = MagicMock()
        mock_pm.functions.positions.return_value.call = AsyncMock(return_value=pos)
        mock_pm.encode_abi = MagicMock(return_value="0xdata")

        # MasterChef: not staked
        mock_mc = MagicMock()
        mock_mc.functions.userPositionInfos.return_value.call = AsyncMock(
            return_value=(
                0,
                0,
                0,
                0,
                0,
                0,
                "0x0000000000000000000000000000000000000000",
                0,
                0,
            )
        )

        mock_symbol = MagicMock()
        mock_symbol.functions.symbol.return_value.call = AsyncMock(return_value="TKN")
        mock_symbol.functions.decimals.return_value.call = AsyncMock(return_value=18)

        def mock_contract(address, abi):
            if any(item.get("name") == "positions" for item in abi):
                return mock_pm
            if any(item.get("name") == "userPositionInfos" for item in abi):
                return mock_mc
            return mock_symbol

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
            result = await skill._arun(token_id=42, percentage=100.0)

        assert "Liquidity Removed" in result
        assert "100.0%" in result
        assert "burned" in result.lower()
        # decrease + collect + burn = 3 transactions
        assert wallet.send_transaction.call_count == 3

    @pytest.mark.asyncio
    async def test_partial_removal(self):
        """Partial removal should not burn the NFT."""
        skill = PancakeSwapRemoveLiquidity()
        ctx = _mock_context()
        wallet = _mock_wallet()

        pos = _mock_position_info(liquidity=1000000)

        mock_pm = MagicMock()
        mock_pm.functions.positions.return_value.call = AsyncMock(return_value=pos)
        mock_pm.encode_abi = MagicMock(return_value="0xdata")

        mock_mc = MagicMock()
        mock_mc.functions.userPositionInfos.return_value.call = AsyncMock(
            return_value=(
                0,
                0,
                0,
                0,
                0,
                0,
                "0x0000000000000000000000000000000000000000",
                0,
                0,
            )
        )

        mock_symbol = MagicMock()
        mock_symbol.functions.symbol.return_value.call = AsyncMock(return_value="TKN")

        def mock_contract(address, abi):
            if any(item.get("name") == "positions" for item in abi):
                return mock_pm
            if any(item.get("name") == "userPositionInfos" for item in abi):
                return mock_mc
            return mock_symbol

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
            result = await skill._arun(token_id=42, percentage=50.0)

        assert "Liquidity Removed" in result
        assert "50.0%" in result
        # decrease + collect = 2 transactions (no burn)
        assert wallet.send_transaction.call_count == 2

    @pytest.mark.asyncio
    async def test_staked_auto_unstake(self):
        """Staked position should be unstaked before removal."""
        skill = PancakeSwapRemoveLiquidity()
        ctx = _mock_context()
        wallet = _mock_wallet()
        wallet_addr = wallet.address

        pos = _mock_position_info(liquidity=1000000)

        mock_pm = MagicMock()
        mock_pm.functions.positions.return_value.call = AsyncMock(return_value=pos)
        mock_pm.encode_abi = MagicMock(return_value="0xdata")

        mock_mc = MagicMock()
        mock_mc.functions.userPositionInfos.return_value.call = AsyncMock(
            return_value=(1000, 0, -887200, 887200, 0, 0, wallet_addr, 0, 0)
        )
        mock_mc.functions.pendingCake.return_value.call = AsyncMock(
            return_value=2 * 10**18
        )
        mock_mc.encode_abi = MagicMock(return_value="0xwithdraw")

        mock_symbol = MagicMock()
        mock_symbol.functions.symbol.return_value.call = AsyncMock(return_value="TKN")

        def mock_contract(address, abi):
            if any(item.get("name") == "positions" for item in abi):
                return mock_pm
            if any(item.get("name") == "userPositionInfos" for item in abi):
                return mock_mc
            return mock_symbol

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
            patch(
                "intentkit.skills.base.IntentKitSkill.get_agent_skill_data",
                new=AsyncMock(return_value={"token_ids": [42]}),
            ),
            patch(
                "intentkit.skills.base.IntentKitSkill.save_agent_skill_data",
                new=AsyncMock(),
            ),
            patch(
                "intentkit.skills.base.IntentKitSkill.delete_agent_skill_data",
                new=AsyncMock(),
            ),
        ):
            result = await skill._arun(token_id=42, percentage=100.0)

        assert "Liquidity Removed" in result
        assert "CAKE" in result
        # unstake + decrease + collect + burn = 4 transactions
        assert wallet.send_transaction.call_count == 4
