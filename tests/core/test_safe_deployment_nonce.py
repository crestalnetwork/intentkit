from unittest.mock import AsyncMock, MagicMock

import pytest

from intentkit.clients.privy import (
    CHAIN_CONFIGS,
    ChainConfig,
    deploy_safe_with_allowance,
)


@pytest.mark.asyncio
async def test_deploy_safe_with_allowance_nonce_threading(monkeypatch):
    """
    Verify that deploy_safe_with_allowance properly threads the nonce
    when enabling module and setting spending limit.
    """
    # Mock mocks
    privy_client = MagicMock()

    # Mock chain config
    chain_config = ChainConfig(
        chain_id=123,
        name="Test Chain",
        safe_tx_service_url="http://safe.tx",
        usdc_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        safe_singleton_address="0xfb1bffC9d739B8D520DaF37dF666da4C687191EA",
        allowance_module_address="0xCFbFaC74C26F8647cBDb8c5caf80BB5b32E43134",
    )
    monkeypatch.setitem(CHAIN_CONFIGS, "test-network", chain_config)

    # Mock SafeClient - need to mock the class itself since it's instantiated inside the function
    mock_safe_client_instance = MagicMock()
    mock_safe_client_instance.predict_safe_address.return_value = "0xSafeAddress"
    mock_safe_client_instance.is_deployed = AsyncMock(return_value=False)
    mock_safe_client_instance._build_safe_initializer.return_value = b"\x00" * 32  # Mock initializer bytes

    mock_safe_client_class = MagicMock(return_value=mock_safe_client_instance)
    monkeypatch.setattr(
        "intentkit.clients.privy_safe.SafeClient", mock_safe_client_class
    )

    # Mock internal helpers

    # _deploy_safe returns (tx_hash, address)
    monkeypatch.setattr(
        "intentkit.clients.privy_safe._deploy_safe",
        AsyncMock(return_value=("0xDeployTx", "0xSafeAddress")),
    )

    # _wait_for_safe_deployed returns True
    monkeypatch.setattr(
        "intentkit.clients.privy_safe._wait_for_safe_deployed", AsyncMock(return_value=True)
    )

    # _is_module_enabled returns False
    monkeypatch.setattr(
        "intentkit.clients.privy_safe._is_module_enabled", AsyncMock(return_value=False)
    )

    # Mock _enable_allowance_module to check if nonce is passed
    mock_enable = AsyncMock(return_value="0xEnableTx")
    monkeypatch.setattr("intentkit.clients.privy_safe._enable_allowance_module", mock_enable)

    # Mock _set_spending_limit to check if nonce is passed
    mock_set_limit = AsyncMock(return_value="0xLimitTx")
    monkeypatch.setattr("intentkit.clients.privy_safe._set_spending_limit", mock_set_limit)

    # Mock _get_safe_nonce - should NOT be called if we just deployed
    mock_get_nonce = AsyncMock(
        return_value=999
    )  # Should not be used if logic is correct (should use 0)
    monkeypatch.setattr("intentkit.clients.privy_safe._get_safe_nonce", mock_get_nonce)

    # ACTION
    await deploy_safe_with_allowance(
        privy_client=privy_client,
        privy_wallet_id="wallet-id",
        privy_wallet_address="0x0000000000000000000000000000000000000000",
        network_id="test-network",
        rpc_url="http://rpc.url",
        weekly_spending_limit_usdc=100.0,
    )

    # ASSERTIONS

    # 1. Verify _enable_allowance_module was called with nonce=0
    mock_enable.assert_awaited_once()
    _, kwargs = mock_enable.call_args
    assert kwargs.get("nonce") == 0, (
        "Should attempt to enable module with nonce 0 (since we just deployed)"
    )

    # 2. Verify _set_spending_limit was called with nonce=1
    mock_set_limit.assert_awaited_once()
    _, kwargs_limit = mock_set_limit.call_args
    assert kwargs_limit.get("nonce") == 1, (
        "Should attempt to set limit with nonce 1 (incremented locally)"
    )

    # 3. Verify logic when already deployed
    # Reset mocks
    mock_safe_client_instance.is_deployed = AsyncMock(return_value=True)
    mock_enable.reset_mock()
    mock_set_limit.reset_mock()
    # If already deployed, it SHOULD call get_nonce
    mock_get_nonce.reset_mock()
    mock_get_nonce.return_value = 5  # Assume current nonce is 5 on chain

    await deploy_safe_with_allowance(
        privy_client=privy_client,
        privy_wallet_id="wallet-id",
        privy_wallet_address="0x0000000000000000000000000000000000000000",
        network_id="test-network",
        rpc_url="http://rpc.url",
        weekly_spending_limit_usdc=100.0,
    )

    mock_get_nonce.assert_awaited_once()

    # Verify _enable_allowance_module was called with nonce=5
    mock_enable.assert_awaited_once()
    _, kwargs = mock_enable.call_args
    assert kwargs.get("nonce") == 5

    # Verify _set_spending_limit was called with nonce=6
    mock_set_limit.assert_awaited_once()
    _, kwargs_limit = mock_set_limit.call_args
    assert kwargs_limit.get("nonce") == 6
