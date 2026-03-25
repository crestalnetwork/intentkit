from unittest.mock import AsyncMock, MagicMock

import pytest

from intentkit.wallets.privy import (
    CHAIN_CONFIGS,
    ChainConfig,
    deploy_safe_with_allowance,
    set_safe_token_spending_limit,
)


@pytest.mark.asyncio
async def testdeploy_safe_with_allowance_nonce_threading(monkeypatch):
    """
    Verify that deploy_safe_with_allowance properly threads the nonce
    when enabling module and setting spending limit.
    """
    privy_client = MagicMock()

    chain_config = ChainConfig(
        chain_id=123,
        name="Test Chain",
        safe_tx_service_url="http://safe.tx",
        usdc_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        safe_singleton_address="0xfb1bffC9d739B8D520DaF37dF666da4C687191EA",
        allowance_module_address="0xCFbFaC74C26F8647cBDb8c5caf80BB5b32E43134",
    )
    monkeypatch.setitem(CHAIN_CONFIGS, "test-network", chain_config)

    mock_safe_client_instance = MagicMock()
    mock_safe_client_instance.predict_safe_address.return_value = (
        "0x00000000000000000000000000000000000000Aa"
    )
    mock_safe_client_instance.is_deployed = AsyncMock(return_value=False)
    mock_safe_client_instance.build_safe_initializer.return_value = b"\x00" * 32

    mock_safe_client_class = MagicMock(return_value=mock_safe_client_instance)
    monkeypatch.setattr(
        "intentkit.wallets.privy_safe.SafeClient", mock_safe_client_class
    )

    monkeypatch.setattr(
        "intentkit.wallets.privy_safe.deploy_safe",
        AsyncMock(
            return_value=("0xDeployTx", "0x00000000000000000000000000000000000000Aa")
        ),
    )

    monkeypatch.setattr(
        "intentkit.wallets.privy_safe.wait_for_safe_deployed",
        AsyncMock(return_value=True),
    )

    mock_set_token_limit = AsyncMock(
        side_effect=[
            {
                "allowance_module_enabled": True,
                "spending_limit_configured": True,
                "tx_hashes": [
                    {"enable_module": "0xEnableTx"},
                    {"set_spending_limit": "0xLimitTx"},
                ],
                "next_nonce": 2,
            },
            {
                "allowance_module_enabled": True,
                "spending_limit_configured": True,
                "tx_hashes": [{"set_spending_limit": "0xLimitTx2"}],
                "next_nonce": 6,
            },
        ]
    )
    monkeypatch.setattr(
        "intentkit.wallets.privy_safe.set_safe_token_spending_limit",
        mock_set_token_limit,
    )

    mock_get_nonce = AsyncMock(return_value=999)
    monkeypatch.setattr("intentkit.wallets.privy_safe.get_safe_nonce", mock_get_nonce)

    await deploy_safe_with_allowance(
        privy_client=privy_client,
        privy_wallet_id="wallet-id",
        privy_wallet_address="0x0000000000000000000000000000000000000000",
        network_id="test-network",
        rpc_url="http://rpc.url",
        weekly_spending_limit_usdc=100.0,
    )

    assert mock_set_token_limit.await_count == 1
    first_kwargs = mock_set_token_limit.await_args_list[0].kwargs
    assert first_kwargs.get("nonce") == 0
    assert first_kwargs.get("token_address") == chain_config.usdc_address
    assert first_kwargs.get("spending_limit") == 100.0

    mock_safe_client_instance.is_deployed = AsyncMock(return_value=True)
    mock_get_nonce.reset_mock()
    mock_get_nonce.return_value = 5

    await deploy_safe_with_allowance(
        privy_client=privy_client,
        privy_wallet_id="wallet-id",
        privy_wallet_address="0x0000000000000000000000000000000000000000",
        network_id="test-network",
        rpc_url="http://rpc.url",
        weekly_spending_limit_usdc=100.0,
    )

    mock_get_nonce.assert_awaited_once()
    assert mock_set_token_limit.await_count == 2
    second_kwargs = mock_set_token_limit.await_args_list[1].kwargs
    assert second_kwargs.get("nonce") == 5


@pytest.mark.asyncio
async def test_set_safe_token_spending_limit_overwrites_same_token(monkeypatch):
    privy_client = MagicMock()

    chain_config = ChainConfig(
        chain_id=123,
        name="Test Chain",
        safe_tx_service_url="http://safe.tx",
        usdc_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        safe_singleton_address="0xfb1bffC9d739B8D520DaF37dF666da4C687191EA",
        allowance_module_address="0xCFbFaC74C26F8647cBDb8c5caf80BB5b32E43134",
    )
    monkeypatch.setitem(CHAIN_CONFIGS, "test-network-overwrite", chain_config)

    monkeypatch.setattr(
        "intentkit.wallets.privy_safe.is_module_enabled",
        AsyncMock(side_effect=[False, True]),
    )
    mock_enable = AsyncMock(return_value="0xEnableTx")
    monkeypatch.setattr(
        "intentkit.wallets.privy_safe.enable_allowance_module",
        mock_enable,
    )
    mock_set_limit = AsyncMock(side_effect=["0xLimitTx1", "0xLimitTx2"])
    monkeypatch.setattr(
        "intentkit.wallets.privy_safe.set_spending_limit",
        mock_set_limit,
    )

    token_address = "0x1111111111111111111111111111111111111111"

    first_result = await set_safe_token_spending_limit(
        privy_client=privy_client,
        privy_wallet_id="wallet-id",
        privy_wallet_address="0x0000000000000000000000000000000000000001",
        safe_address="0x0000000000000000000000000000000000000002",
        token_address=token_address,
        spending_limit=100.0,
        token_decimals=6,
        network_id="test-network-overwrite",
        rpc_url="http://rpc.url",
        nonce=7,
    )
    second_result = await set_safe_token_spending_limit(
        privy_client=privy_client,
        privy_wallet_id="wallet-id",
        privy_wallet_address="0x0000000000000000000000000000000000000001",
        safe_address="0x0000000000000000000000000000000000000002",
        token_address=token_address,
        spending_limit=250.0,
        token_decimals=6,
        network_id="test-network-overwrite",
        rpc_url="http://rpc.url",
        nonce=9,
    )

    mock_enable.assert_awaited_once()
    assert mock_set_limit.await_count == 2

    first_kwargs = mock_set_limit.await_args_list[0].kwargs
    second_kwargs = mock_set_limit.await_args_list[1].kwargs
    assert first_kwargs["token_address"].lower() == token_address.lower()
    assert second_kwargs["token_address"].lower() == token_address.lower()
    assert first_kwargs["allowance_amount"] == 100_000_000
    assert second_kwargs["allowance_amount"] == 250_000_000
    assert first_kwargs["nonce"] == 8
    assert second_kwargs["nonce"] == 9
    assert first_result["next_nonce"] == 9
    assert second_result["next_nonce"] == 10


@pytest.mark.asyncio
async def test_set_safe_token_spending_limit_supports_multiple_tokens(monkeypatch):
    privy_client = MagicMock()

    chain_config = ChainConfig(
        chain_id=123,
        name="Test Chain",
        safe_tx_service_url="http://safe.tx",
        usdc_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        safe_singleton_address="0xfb1bffC9d739B8D520DaF37dF666da4C687191EA",
        allowance_module_address="0xCFbFaC74C26F8647cBDb8c5caf80BB5b32E43134",
    )
    monkeypatch.setitem(CHAIN_CONFIGS, "test-network-multi-token", chain_config)

    monkeypatch.setattr(
        "intentkit.wallets.privy_safe.is_module_enabled",
        AsyncMock(side_effect=[True, True]),
    )
    mock_enable = AsyncMock(return_value="0xEnableTx")
    monkeypatch.setattr(
        "intentkit.wallets.privy_safe.enable_allowance_module",
        mock_enable,
    )
    mock_set_limit = AsyncMock(side_effect=["0xTokenATx", "0xTokenBTx"])
    monkeypatch.setattr(
        "intentkit.wallets.privy_safe.set_spending_limit",
        mock_set_limit,
    )

    token_a = "0x1111111111111111111111111111111111111111"
    token_b = "0x2222222222222222222222222222222222222222"

    await set_safe_token_spending_limit(
        privy_client=privy_client,
        privy_wallet_id="wallet-id",
        privy_wallet_address="0x0000000000000000000000000000000000000001",
        safe_address="0x0000000000000000000000000000000000000002",
        token_address=token_a,
        spending_limit=10.0,
        token_decimals=6,
        network_id="test-network-multi-token",
        rpc_url="http://rpc.url",
        nonce=1,
    )
    await set_safe_token_spending_limit(
        privy_client=privy_client,
        privy_wallet_id="wallet-id",
        privy_wallet_address="0x0000000000000000000000000000000000000001",
        safe_address="0x0000000000000000000000000000000000000002",
        token_address=token_b,
        spending_limit=20.0,
        token_decimals=6,
        network_id="test-network-multi-token",
        rpc_url="http://rpc.url",
        nonce=2,
    )

    mock_enable.assert_not_awaited()
    assert mock_set_limit.await_count == 2
    assert mock_set_limit.await_args_list[0].kwargs["token_address"].lower() == token_a
    assert mock_set_limit.await_args_list[1].kwargs["token_address"].lower() == token_b


@pytest.mark.asyncio
async def test_set_safe_token_spending_limit_reads_decimals_via_network_id(monkeypatch):
    """Verify _get_erc20_decimals uses get_async_web3_client(network_id), not raw rpc_url."""
    privy_client = MagicMock()
    chain_config = ChainConfig(
        chain_id=123,
        name="Test Chain",
        safe_tx_service_url="http://safe.tx",
        usdc_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        safe_singleton_address="0xfb1bffC9d739B8D520DaF37dF666da4C687191EA",
        allowance_module_address="0xCFbFaC74C26F8647cBDb8c5caf80BB5b32E43134",
    )
    monkeypatch.setitem(CHAIN_CONFIGS, "test-network-decimals", chain_config)
    monkeypatch.setattr(
        "intentkit.wallets.privy_safe.is_module_enabled",
        AsyncMock(return_value=True),
    )
    mock_set_limit = AsyncMock(return_value="0xLimitTx")
    monkeypatch.setattr(
        "intentkit.wallets.privy_safe.set_spending_limit", mock_set_limit
    )

    mock_contract = MagicMock()
    mock_contract.functions.decimals.return_value.call = AsyncMock(return_value=6)
    mock_web3_instance = MagicMock()
    mock_web3_instance.eth.contract.return_value = mock_contract
    mock_get_web3 = MagicMock(return_value=mock_web3_instance)
    monkeypatch.setattr(
        "intentkit.wallets.privy_safe.get_async_web3_client", mock_get_web3
    )

    result = await set_safe_token_spending_limit(
        privy_client=privy_client,
        privy_wallet_id="wallet-id",
        privy_wallet_address="0x0000000000000000000000000000000000000001",
        safe_address="0x0000000000000000000000000000000000000002",
        token_address="0x1111111111111111111111111111111111111111",
        spending_limit=100.0,
        network_id="test-network-decimals",
        rpc_url="http://rpc.url",
        nonce=3,
    )

    assert result["spending_limit_configured"] is True
    assert mock_set_limit.await_args_list[0].kwargs["allowance_amount"] == 100_000_000
    mock_get_web3.assert_called_once_with("test-network-decimals")
