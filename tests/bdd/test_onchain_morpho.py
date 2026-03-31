"""BDD tests for on-chain Morpho read-only skills using real RPC."""

import os

import pytest
import pytest_asyncio
from web3 import AsyncWeb3

from intentkit.skills.erc20.constants import ERC20_ABI
from intentkit.skills.morpho.constants import (
    METAMORPHO_ABI,
    MORPHO_BLUE_ABI,
    MORPHO_BLUE_ADDRESS,
)

NETWORK = "base-mainnet"
# Moonwell Flagship USDC vault on Base (well-known MetaMorpho vault)
METAMORPHO_USDC_VAULT = "0xc1256Ae5FF1cf2719D4937adb3bbCCab2E00A2Ca"
# An address with no Morpho position
EMPTY_ADDRESS = "0x0000000000000000000000000000000000000001"


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


# ── MetaMorpho Vault reads ──


@pytest.mark.asyncio
async def test_morpho_vault_total_assets(w3: AsyncWeb3):
    """totalAssets should return a non-negative integer."""
    vault = w3.eth.contract(
        address=w3.to_checksum_address(METAMORPHO_USDC_VAULT),
        abi=METAMORPHO_ABI,
    )
    total_assets = await vault.functions.totalAssets().call()
    assert isinstance(total_assets, int)
    assert total_assets >= 0


@pytest.mark.asyncio
async def test_morpho_vault_asset(w3: AsyncWeb3):
    """asset() should return a valid ERC20 address (USDC for this vault)."""
    vault = w3.eth.contract(
        address=w3.to_checksum_address(METAMORPHO_USDC_VAULT),
        abi=METAMORPHO_ABI,
    )
    asset_address = await vault.functions.asset().call()
    assert asset_address != "0x0000000000000000000000000000000000000000"
    # Verify the underlying token is USDC by checking its symbol
    token = w3.eth.contract(
        address=w3.to_checksum_address(asset_address),
        abi=ERC20_ABI,
    )
    symbol = await token.functions.symbol().call()
    assert symbol == "USDC"


@pytest.mark.asyncio
async def test_morpho_vault_total_supply(w3: AsyncWeb3):
    """totalSupply should return a non-negative integer."""
    vault = w3.eth.contract(
        address=w3.to_checksum_address(METAMORPHO_USDC_VAULT),
        abi=METAMORPHO_ABI,
    )
    total_supply = await vault.functions.totalSupply().call()
    assert isinstance(total_supply, int)
    assert total_supply >= 0


@pytest.mark.asyncio
async def test_morpho_vault_convert_to_assets(w3: AsyncWeb3):
    """convertToAssets should return a positive value for 1 share."""
    vault = w3.eth.contract(
        address=w3.to_checksum_address(METAMORPHO_USDC_VAULT),
        abi=METAMORPHO_ABI,
    )
    one_share = 10**18
    assets_per_share = await vault.functions.convertToAssets(one_share).call()
    assert isinstance(assets_per_share, int)
    # Share price should be >= 1 USDC (10^6) for a healthy vault
    assert assets_per_share > 0


@pytest.mark.asyncio
async def test_morpho_vault_balance_of(w3: AsyncWeb3):
    """balanceOf for empty address should be 0."""
    vault = w3.eth.contract(
        address=w3.to_checksum_address(METAMORPHO_USDC_VAULT),
        abi=METAMORPHO_ABI,
    )
    balance = await vault.functions.balanceOf(
        w3.to_checksum_address(EMPTY_ADDRESS)
    ).call()
    assert balance == 0


# ── Morpho Blue reads ──


@pytest.mark.asyncio
async def test_morpho_blue_position_empty(w3: AsyncWeb3):
    """position() for empty address should return all zeros."""
    morpho = w3.eth.contract(
        address=w3.to_checksum_address(MORPHO_BLUE_ADDRESS),
        abi=MORPHO_BLUE_ABI,
    )
    # Use a known market ID (USDC/WETH on Base - this is a common one)
    # We just need any valid bytes32; if market doesn't exist, position is still (0,0,0)
    dummy_market_id = bytes(32)  # all zeros

    result = await morpho.functions.position(
        dummy_market_id,
        w3.to_checksum_address(EMPTY_ADDRESS),
    ).call()

    supply_shares, borrow_shares, collateral = result
    assert supply_shares == 0
    assert borrow_shares == 0
    assert collateral == 0


@pytest.mark.asyncio
async def test_morpho_blue_market_data(w3: AsyncWeb3):
    """market() for a zero market ID should return all zeros (non-existent market)."""
    morpho = w3.eth.contract(
        address=w3.to_checksum_address(MORPHO_BLUE_ADDRESS),
        abi=MORPHO_BLUE_ABI,
    )
    dummy_market_id = bytes(32)

    result = await morpho.functions.market(dummy_market_id).call()

    assert len(result) == 6
    (
        total_supply_assets,
        total_supply_shares,
        _total_borrow_assets,
        _total_borrow_shares,
        _last_update,
        _fee,
    ) = result
    assert total_supply_assets == 0
    assert total_supply_shares == 0
