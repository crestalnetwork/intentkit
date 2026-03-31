"""BDD tests for on-chain Uniswap V3 read-only skills using real RPC."""

import os

import pytest
import pytest_asyncio
from web3 import AsyncWeb3

from intentkit.skills.erc20.constants import TOKEN_ADDRESSES_BY_SYMBOLS
from intentkit.skills.uniswap.constants import (
    FACTORY_ABI,
    FACTORY_ADDRESSES,
    NETWORK_TO_CHAIN_ID,
    POSITION_MANAGER_ABI,
    POSITION_MANAGER_ADDRESSES,
    QUOTER_V2_ABI,
    QUOTER_V2_ADDRESSES,
    WRAPPED_NATIVE_ADDRESSES,
)
from intentkit.skills.uniswap.utils import convert_amount, resolve_token

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
    """'native' should resolve to the wrapped native address."""
    addr = resolve_token("native", CHAIN_ID)
    assert addr == WETH_ADDRESS


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


# ── On-chain reads: Factory ──


@pytest.mark.asyncio
async def test_uniswap_factory_get_pool(w3: AsyncWeb3):
    """getPool for USDC/WETH at 500 bps should return a non-zero pool address."""
    factory_address = FACTORY_ADDRESSES[CHAIN_ID]
    factory = w3.eth.contract(
        address=w3.to_checksum_address(factory_address),
        abi=FACTORY_ABI,
    )

    pool = await factory.functions.getPool(
        w3.to_checksum_address(USDC_ADDRESS),
        w3.to_checksum_address(WETH_ADDRESS),
        500,  # 0.05% fee tier
    ).call()

    assert pool != "0x0000000000000000000000000000000000000000"


@pytest.mark.asyncio
async def test_uniswap_factory_get_pool_nonexistent(w3: AsyncWeb3):
    """getPool for a non-existent pair should return zero address."""
    factory_address = FACTORY_ADDRESSES[CHAIN_ID]
    factory = w3.eth.contract(
        address=w3.to_checksum_address(factory_address),
        abi=FACTORY_ABI,
    )

    # Use zero address as token - no pool should exist
    pool = await factory.functions.getPool(
        w3.to_checksum_address("0x0000000000000000000000000000000000000001"),
        w3.to_checksum_address("0x0000000000000000000000000000000000000002"),
        500,
    ).call()

    assert pool == "0x0000000000000000000000000000000000000000"


# ── On-chain reads: QuoterV2 ──


@pytest.mark.asyncio
async def test_uniswap_quote_usdc_weth(w3: AsyncWeb3):
    """Quoting 1000 USDC -> WETH should return a positive amount."""
    quoter_address = QUOTER_V2_ADDRESSES[CHAIN_ID]
    quoter = w3.eth.contract(
        address=w3.to_checksum_address(quoter_address),
        abi=QUOTER_V2_ABI,
    )

    amount_in = convert_amount("1000", 6)  # 1000 USDC

    # Try 500 bps fee tier (common for USDC/WETH)
    result = await quoter.functions.quoteExactInputSingle(
        (
            w3.to_checksum_address(USDC_ADDRESS),
            w3.to_checksum_address(WETH_ADDRESS),
            amount_in,
            500,
            0,
        )
    ).call()

    amount_out = result[0]
    gas_estimate = result[3]

    # Should get some WETH back
    assert amount_out > 0
    assert gas_estimate > 0


# ── On-chain reads: PositionManager ──


@pytest.mark.asyncio
async def test_uniswap_position_manager_balance(w3: AsyncWeb3):
    """balanceOf should return a non-negative integer."""
    pm_address = POSITION_MANAGER_ADDRESSES[CHAIN_ID]
    pm = w3.eth.contract(
        address=w3.to_checksum_address(pm_address),
        abi=POSITION_MANAGER_ABI,
    )

    balance = await pm.functions.balanceOf(w3.to_checksum_address(EMPTY_ADDRESS)).call()
    assert isinstance(balance, int)
    assert balance >= 0
