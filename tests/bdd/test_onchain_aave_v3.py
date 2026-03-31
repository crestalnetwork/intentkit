"""BDD tests for on-chain Aave V3 read-only skills using real RPC."""

import os

import pytest
import pytest_asyncio
from web3 import AsyncWeb3

from intentkit.skills.aave_v3.constants import (
    NETWORK_TO_CHAIN_ID,
    POOL_ABI,
    POOL_ADDRESSES,
    POOL_DATA_PROVIDER_ABI,
    POOL_DATA_PROVIDER_ADDRESSES,
)
from intentkit.skills.aave_v3.utils import (
    format_amount,
    format_base_currency,
    format_health_factor,
    format_ray,
)
from intentkit.skills.erc20.constants import TOKEN_ADDRESSES_BY_SYMBOLS

NETWORK = "base-mainnet"
CHAIN_ID = NETWORK_TO_CHAIN_ID[NETWORK]
USDC_ADDRESS = TOKEN_ADDRESSES_BY_SYMBOLS[NETWORK]["USDC"]
# An address with no Aave position
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


# ── Utility function tests (no RPC needed) ──


def test_format_amount():
    """format_amount should convert raw value to human-readable."""
    assert format_amount(1_000_000, 6) == "1"
    assert format_amount(1_500_000_000_000_000_000, 18) == "1.5"


def test_format_ray():
    """format_ray should convert RAY value to percentage string."""
    one_pct_ray = 10**27 // 100
    result = format_ray(one_pct_ray)
    assert result == "1.00%"


def test_format_health_factor_infinity():
    """MAX_UINT256 health factor should show infinity."""
    result = format_health_factor(2**256 - 1)
    assert "∞" in result


def test_format_health_factor_normal():
    """Normal health factor should format to 4 decimal places."""
    # 1.5 with 18 decimals
    result = format_health_factor(1_500_000_000_000_000_000)
    assert "1.5000" in result


def test_format_base_currency():
    """format_base_currency should convert 8-decimal USD value."""
    result = format_base_currency(100_000_000)
    assert "$1" in result


# ── On-chain reads: getReserveData ──


@pytest.mark.asyncio
async def test_aave_get_reserve_data(w3: AsyncWeb3):
    """getReserveData for USDC on Base should return valid market data."""
    provider_address = POOL_DATA_PROVIDER_ADDRESSES[CHAIN_ID]
    provider = w3.eth.contract(
        address=w3.to_checksum_address(provider_address),
        abi=POOL_DATA_PROVIDER_ABI,
    )

    result = await provider.functions.getReserveData(
        w3.to_checksum_address(USDC_ADDRESS)
    ).call()

    assert len(result) == 12
    # Unpack to verify types
    (
        _unbacked,
        _accrued_to_treasury,
        total_atoken,
        _total_stable_debt,
        _total_variable_debt,
        liquidity_rate,
        variable_borrow_rate,
        _stable_borrow_rate,
        _avg_stable_rate,
        _liquidity_index,
        _variable_borrow_index,
        _last_update,
    ) = result

    # total_atoken (total supplied) should be > 0 for USDC on Aave Base
    assert total_atoken > 0
    # Rates should be non-negative
    assert liquidity_rate >= 0
    assert variable_borrow_rate >= 0


@pytest.mark.asyncio
async def test_aave_get_reserve_configuration_data(w3: AsyncWeb3):
    """getReserveConfigurationData for USDC should return valid config."""
    provider_address = POOL_DATA_PROVIDER_ADDRESSES[CHAIN_ID]
    provider = w3.eth.contract(
        address=w3.to_checksum_address(provider_address),
        abi=POOL_DATA_PROVIDER_ABI,
    )

    result = await provider.functions.getReserveConfigurationData(
        w3.to_checksum_address(USDC_ADDRESS)
    ).call()

    assert len(result) == 10
    (
        decimals,
        ltv,
        liq_threshold,
        _liq_bonus,
        _reserve_factor,
        _collateral_enabled,
        _borrowing_enabled,
        _stable_borrow_enabled,
        is_active,
        _is_frozen,
    ) = result

    # USDC has 6 decimals
    assert decimals == 6
    # USDC should be active on Aave Base
    assert is_active is True
    # LTV should be a reasonable percentage (expressed in bps, e.g. 7500 = 75%)
    assert 0 < ltv <= 10000
    assert 0 < liq_threshold <= 10000


# ── On-chain reads: getUserAccountData ──


@pytest.mark.asyncio
async def test_aave_get_user_account_data_empty(w3: AsyncWeb3):
    """getUserAccountData for empty address should return all zeros."""
    pool_address = POOL_ADDRESSES[CHAIN_ID]
    pool = w3.eth.contract(
        address=w3.to_checksum_address(pool_address),
        abi=POOL_ABI,
    )

    result = await pool.functions.getUserAccountData(
        w3.to_checksum_address(EMPTY_ADDRESS)
    ).call()

    assert len(result) == 6
    (
        total_collateral,
        total_debt,
        available_borrows,
        _liq_threshold,
        _ltv,
        _health_factor,
    ) = result

    # Empty address should have no collateral or debt
    assert total_collateral == 0
    assert total_debt == 0
    assert available_borrows == 0
