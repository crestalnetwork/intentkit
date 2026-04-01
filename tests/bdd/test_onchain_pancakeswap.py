"""BDD tests for on-chain PancakeSwap V3 read-only skills using real RPC."""

import os

import pytest
import pytest_asyncio
from web3 import AsyncWeb3

from intentkit.skills.erc20.constants import TOKEN_ADDRESSES_BY_SYMBOLS
from intentkit.skills.pancakeswap.constants import (
    FACTORY_ABI,
    FACTORY_ADDRESS,
    FEE_TIERS,
    MASTERCHEF_V3_ABI,
    MASTERCHEF_V3_ADDRESSES,
    NETWORK_TO_CHAIN_ID,
    POSITION_MANAGER_ABI,
    POSITION_MANAGER_ADDRESS,
    QUOTER_V2_ABI,
    QUOTER_V2_ADDRESSES,
    WRAPPED_NATIVE_ADDRESSES,
)
from intentkit.skills.pancakeswap.utils import (
    convert_amount,
    format_amount,
    resolve_token,
)

NETWORK = "base-mainnet"
CHAIN_ID = NETWORK_TO_CHAIN_ID[NETWORK]
USDC_ADDRESS = TOKEN_ADDRESSES_BY_SYMBOLS[NETWORK]["USDC"]
WETH_ADDRESS = WRAPPED_NATIVE_ADDRESSES[CHAIN_ID]
EMPTY_ADDRESS = "0x000000000000000000000000000000000000dEaD"


@pytest_asyncio.fixture(scope="module")
async def w3():
    """Create a real AsyncWeb3 client from env config."""
    infura_key = os.getenv("INFURA_API_KEY")
    if not infura_key:
        pytest.skip("No INFURA_API_KEY configured")

    rpc_url = f"https://base-mainnet.infura.io/v3/{infura_key}"
    provider = AsyncWeb3.AsyncHTTPProvider(rpc_url)
    client = AsyncWeb3(provider)

    connected = await client.is_connected()
    if not connected:
        pytest.skip("Cannot connect to RPC provider")

    return client


# ── Utility function tests (no RPC needed) ──


def test_resolve_token_native():
    """'native' should resolve to the wrapped native address for the chain."""
    addr = resolve_token("native", CHAIN_ID)
    assert addr == WETH_ADDRESS


def test_resolve_token_native_bsc():
    """'native' on BSC should resolve to WBNB."""
    bsc_chain_id = NETWORK_TO_CHAIN_ID["bnb-mainnet"]
    addr = resolve_token("native", bsc_chain_id)
    assert addr == WRAPPED_NATIVE_ADDRESSES[bsc_chain_id]


def test_resolve_token_address():
    """A non-native token should pass through unchanged."""
    addr = resolve_token(USDC_ADDRESS, CHAIN_ID)
    assert addr == USDC_ADDRESS


def test_convert_amount():
    """convert_amount should produce correct raw integer."""
    raw = convert_amount("1.5", 6)
    assert raw == 1_500_000

    raw = convert_amount("1", 18)
    assert raw == 10**18


def test_convert_amount_rejects_zero():
    """convert_amount should reject zero or negative amounts."""
    with pytest.raises(Exception):
        convert_amount("0", 6)


def test_format_amount():
    """format_amount should convert raw integer back to human-readable string."""
    assert format_amount(1_500_000, 6) == "1.5"
    assert format_amount(10**18, 18) == "1"


# ── On-chain reads: Factory ──


@pytest.mark.asyncio
async def test_pancakeswap_factory_get_pool(w3: AsyncWeb3):
    """getPool for USDC/WETH at 500 bps should return a non-zero pool address."""
    factory = w3.eth.contract(
        address=w3.to_checksum_address(FACTORY_ADDRESS),
        abi=FACTORY_ABI,
    )

    pool = await factory.functions.getPool(
        w3.to_checksum_address(USDC_ADDRESS),
        w3.to_checksum_address(WETH_ADDRESS),
        500,  # 0.05% fee tier
    ).call()

    assert pool != "0x0000000000000000000000000000000000000000"


@pytest.mark.asyncio
async def test_pancakeswap_factory_get_pool_nonexistent(w3: AsyncWeb3):
    """getPool for a non-existent pair should return zero address."""
    factory = w3.eth.contract(
        address=w3.to_checksum_address(FACTORY_ADDRESS),
        abi=FACTORY_ABI,
    )

    pool = await factory.functions.getPool(
        w3.to_checksum_address("0x0000000000000000000000000000000000000001"),
        w3.to_checksum_address("0x0000000000000000000000000000000000000002"),
        500,
    ).call()

    assert pool == "0x0000000000000000000000000000000000000000"


# ── On-chain reads: QuoterV2 ──


@pytest.mark.asyncio
async def test_pancakeswap_quote_usdc_weth(w3: AsyncWeb3):
    """Quoting 1000 USDC -> WETH should return a positive amount on at least one fee tier."""
    quoter_address = QUOTER_V2_ADDRESSES[CHAIN_ID]
    quoter = w3.eth.contract(
        address=w3.to_checksum_address(quoter_address),
        abi=QUOTER_V2_ABI,
    )

    amount_in = convert_amount("1000", 6)  # 1000 USDC

    best_out = 0
    for fee in FEE_TIERS:
        try:
            result = await quoter.functions.quoteExactInputSingle(
                (
                    w3.to_checksum_address(USDC_ADDRESS),
                    w3.to_checksum_address(WETH_ADDRESS),
                    amount_in,
                    fee,
                    0,
                )
            ).call()
            amount_out = result[0]
            if amount_out > best_out:
                best_out = amount_out
        except Exception:
            continue

    assert best_out > 0


@pytest.mark.asyncio
async def test_pancakeswap_quote_result_fields(w3: AsyncWeb3):
    """Quote result should have 4 fields: amountOut, sqrtPriceX96After, ticksCrossed, gasEstimate."""
    quoter_address = QUOTER_V2_ADDRESSES[CHAIN_ID]
    quoter = w3.eth.contract(
        address=w3.to_checksum_address(quoter_address),
        abi=QUOTER_V2_ABI,
    )

    amount_in = convert_amount("100", 6)  # 100 USDC

    result = None
    for fee in FEE_TIERS:
        try:
            result = await quoter.functions.quoteExactInputSingle(
                (
                    w3.to_checksum_address(USDC_ADDRESS),
                    w3.to_checksum_address(WETH_ADDRESS),
                    amount_in,
                    fee,
                    0,
                )
            ).call()
            if result[0] > 0:
                break
        except Exception:
            continue

    assert result is not None
    assert len(result) == 4
    amount_out, sqrt_price_after, ticks_crossed, gas_estimate = result
    assert amount_out > 0
    assert sqrt_price_after > 0
    assert gas_estimate > 0


# ── On-chain reads: PositionManager ──


@pytest.mark.asyncio
async def test_pancakeswap_position_manager_balance(w3: AsyncWeb3):
    """balanceOf should return a non-negative integer."""
    pm = w3.eth.contract(
        address=w3.to_checksum_address(POSITION_MANAGER_ADDRESS),
        abi=POSITION_MANAGER_ABI,
    )

    balance = await pm.functions.balanceOf(w3.to_checksum_address(EMPTY_ADDRESS)).call()
    assert isinstance(balance, int)
    assert balance >= 0


# ── On-chain reads: MasterChef V3 ──


@pytest.mark.asyncio
async def test_pancakeswap_masterchef_pending_cake(w3: AsyncWeb3):
    """pendingCake for a non-existent tokenId should return 0 or revert gracefully."""
    masterchef_addr = MASTERCHEF_V3_ADDRESSES.get(CHAIN_ID)
    if not masterchef_addr:
        pytest.skip(f"No MasterChef V3 address for chain {CHAIN_ID}")

    mc = w3.eth.contract(
        address=w3.to_checksum_address(masterchef_addr),
        abi=MASTERCHEF_V3_ABI,
    )

    # Use a very large tokenId that almost certainly doesn't exist
    try:
        pending = await mc.functions.pendingCake(999_999_999).call()
        assert isinstance(pending, int)
        assert pending >= 0
    except Exception:
        # Some MasterChef implementations revert for non-existent tokenIds
        pass
