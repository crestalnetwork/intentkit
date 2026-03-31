"""BDD tests for on-chain ERC20 read-only skills using real RPC."""

import os

import pytest
import pytest_asyncio
from web3 import AsyncWeb3

from intentkit.skills.erc20.constants import ERC20_ABI, TOKEN_ADDRESSES_BY_SYMBOLS
from intentkit.skills.erc20.utils import (
    get_available_token_symbols,
    get_token_address_by_symbol,
)

# USDC on Base mainnet - a stable, well-known contract
NETWORK = "base-mainnet"
USDC_ADDRESS = TOKEN_ADDRESSES_BY_SYMBOLS[NETWORK]["USDC"]
# Coinbase's known address on Base (has USDC balance)
KNOWN_ADDRESS = "0xcdac0d6c6c59727a65f871236188350531885c43"


@pytest_asyncio.fixture(scope="module")
async def w3():
    """Create a real AsyncWeb3 client from env config."""
    infura_key = os.getenv("INFURA_API_KEY")
    quicknode_key = os.getenv("QUICKNODE_API_KEY")

    if infura_key:
        rpc_url = f"https://base-mainnet.infura.io/v3/{infura_key}"
    elif quicknode_key:
        pytest.skip("QuickNode requires endpoint URL, not just API key")
    else:
        pytest.skip("No RPC provider configured (INFURA_API_KEY or QUICKNODE_API_KEY)")

    provider = AsyncWeb3.AsyncHTTPProvider(rpc_url)
    client = AsyncWeb3(provider)

    # Verify connection
    connected = await client.is_connected()
    if not connected:
        pytest.skip("Cannot connect to RPC provider")

    return client


# ── Token address lookup (pure utility, no RPC needed) ──


def test_get_token_address_by_symbol_found():
    """Known token symbols should resolve to addresses."""
    address = get_token_address_by_symbol(NETWORK, "USDC")
    assert address is not None
    assert address == USDC_ADDRESS


def test_get_token_address_by_symbol_case_insensitive():
    """Symbol lookup should be case-insensitive."""
    address = get_token_address_by_symbol(NETWORK, "usdc")
    assert address == USDC_ADDRESS


def test_get_token_address_by_symbol_not_found():
    """Unknown symbol should return None."""
    address = get_token_address_by_symbol(NETWORK, "DOESNOTEXIST")
    assert address is None


def test_get_available_token_symbols():
    """Should return known symbols for Base mainnet."""
    symbols = get_available_token_symbols(NETWORK)
    assert "USDC" in symbols
    assert "WETH" in symbols
    assert len(symbols) > 0


# ── On-chain reads via real RPC ──


@pytest.mark.asyncio
async def test_erc20_name(w3: AsyncWeb3):
    """Query the name of USDC on Base."""
    contract = w3.eth.contract(
        address=w3.to_checksum_address(USDC_ADDRESS),
        abi=ERC20_ABI,
    )
    name = await contract.functions.name().call()
    assert name == "USD Coin"


@pytest.mark.asyncio
async def test_erc20_symbol(w3: AsyncWeb3):
    """Query the symbol of USDC on Base."""
    contract = w3.eth.contract(
        address=w3.to_checksum_address(USDC_ADDRESS),
        abi=ERC20_ABI,
    )
    symbol = await contract.functions.symbol().call()
    assert symbol == "USDC"


@pytest.mark.asyncio
async def test_erc20_decimals(w3: AsyncWeb3):
    """USDC should have 6 decimals."""
    contract = w3.eth.contract(
        address=w3.to_checksum_address(USDC_ADDRESS),
        abi=ERC20_ABI,
    )
    decimals = await contract.functions.decimals().call()
    assert decimals == 6


@pytest.mark.asyncio
async def test_erc20_balance_of(w3: AsyncWeb3):
    """balanceOf should return a non-negative integer."""
    contract = w3.eth.contract(
        address=w3.to_checksum_address(USDC_ADDRESS),
        abi=ERC20_ABI,
    )
    balance = await contract.functions.balanceOf(
        w3.to_checksum_address(KNOWN_ADDRESS)
    ).call()
    assert isinstance(balance, int)
    assert balance >= 0


@pytest.mark.asyncio
async def test_erc20_balance_of_zero_address(w3: AsyncWeb3):
    """Zero address should return a valid balance (typically 0 or burn amount)."""
    contract = w3.eth.contract(
        address=w3.to_checksum_address(USDC_ADDRESS),
        abi=ERC20_ABI,
    )
    zero_addr = "0x0000000000000000000000000000000000000000"
    balance = await contract.functions.balanceOf(
        w3.to_checksum_address(zero_addr)
    ).call()
    assert isinstance(balance, int)
    assert balance >= 0
