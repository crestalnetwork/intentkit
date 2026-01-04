#!/usr/bin/env python
"""
Test script for Privy + Safe wallet integration.

This script tests the wallet creation and Safe deployment flow.
"""

import asyncio
import logging
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to path
sys.path.append(os.getcwd())

from intentkit.config.config import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_wallet_creation_flow():
    """Test the basic wallet creation flow with mocked APIs."""
    logger.info("Testing create_privy_safe_wallet flow...")

    # Import after path setup
    from intentkit.clients.privy import (
        SafeClient,
        create_privy_safe_wallet,
    )

    # Mock Config
    config.privy_app_id = "test_app_id"
    config.privy_app_secret = "test_app_secret"
    config.safe_api_key = "test_safe_api_key"

    # Mock Data
    agent_id = "test_agent_123"
    network_id = "base-mainnet"
    mock_privy_wallet_response = {
        "id": "privy_wallet_id_123",
        "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
        "chain_type": "ethereum",
    }

    # Predict what the Safe address should be
    safe_client = SafeClient(network_id)
    from eth_utils import keccak

    salt_nonce = int.from_bytes(keccak(text="privy_wallet_id_123")[:8], "big")
    expected_safe_address = safe_client.predict_safe_address(
        owner_address=mock_privy_wallet_response["address"],
        salt_nonce=salt_nonce,
        threshold=1,
    )

    logger.info(f"Expected Safe address: {expected_safe_address}")

    # Mock httpx.AsyncClient
    with patch("intentkit.clients.privy.httpx.AsyncClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        call_count = 0

        async def mock_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            mock_response.status_code = 200

            if "privy.io" in url and "/wallets" in url and "/rpc" not in url:
                # Create wallet call
                logger.info(f"[{call_count}] Mocked Privy create wallet: {url}")
                mock_response.status_code = 201
                mock_response.json.return_value = mock_privy_wallet_response
            elif "privy.io" in url and "/rpc" in url:
                # Sign or send transaction call
                logger.info(f"[{call_count}] Mocked Privy RPC call: {url}")
                mock_response.json.return_value = {
                    "data": {
                        "hash": "0x" + "ab" * 32,
                        "signature": "0x" + "cd" * 65,
                    }
                }
            elif "eth_getCode" in str(kwargs.get("json", {})):
                # Check deployment - first return not deployed, then deployed
                logger.info(f"[{call_count}] Mocked eth_getCode call")
                if call_count < 5:
                    mock_response.json.return_value = {"result": "0x"}
                else:
                    mock_response.json.return_value = {"result": "0x" + "ff" * 100}
            elif "eth_call" in str(kwargs.get("json", {})):
                # Contract calls (isModuleEnabled, etc)
                logger.info(f"[{call_count}] Mocked eth_call")
                mock_response.json.return_value = {"result": "0x" + "00" * 32}
            else:
                logger.info(f"[{call_count}] Mocked unknown call to: {url}")
                mock_response.json.return_value = {}

            return mock_response

        mock_client.post = mock_post
        mock_client.get = AsyncMock(
            return_value=MagicMock(status_code=404, json=lambda: None)
        )

        # Execute without spending limit (simpler test)
        result = await create_privy_safe_wallet(
            agent_id=agent_id,
            network_id=network_id,
            rpc_url="https://mock-rpc.example.com",
            weekly_spending_limit_usdc=None,  # Skip spending limit for basic test
        )

        # Verify
        logger.info("Result: %s", result)

        assert result["privy_wallet_id"] == "privy_wallet_id_123"
        assert (
            result["privy_wallet_address"]
            == "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21"
        )
        assert result["provider"] == "safe"
        assert result["network_id"] == "base-mainnet"
        assert result["chain_id"] == 8453
        assert "smart_wallet_address" in result
        assert result["smart_wallet_address"].startswith("0x")
        assert len(result["smart_wallet_address"]) == 42
        assert "salt_nonce" in result
        assert "deployment_info" in result

        logger.info("Smart wallet address (Safe): %s", result["smart_wallet_address"])
        logger.info("Salt nonce: %s", result["salt_nonce"])
        logger.info("Verification PASSED!")


async def test_address_prediction_determinism():
    """Test that Safe address prediction is deterministic for the same inputs."""
    logger.info("Testing Safe address prediction determinism...")

    from intentkit.clients.privy import SafeClient

    safe_client = SafeClient("base-mainnet")
    owner_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21"

    # Same inputs should produce same address
    address1 = safe_client.predict_safe_address(owner_address, salt_nonce=0)
    address2 = safe_client.predict_safe_address(owner_address, salt_nonce=0)

    assert address1 == address2, "Address prediction should be deterministic"
    logger.info(f"Predicted address (salt_nonce=0): {address1}")

    # Different salt nonce should produce different address
    address3 = safe_client.predict_safe_address(owner_address, salt_nonce=1)
    assert address1 != address3, "Different salt nonce should produce different address"
    logger.info(f"Predicted address (salt_nonce=1): {address3}")

    # Different owner should produce different address
    address4 = safe_client.predict_safe_address(
        "0x1234567890123456789012345678901234567890", salt_nonce=0
    )
    assert address1 != address4, "Different owner should produce different address"
    logger.info(f"Predicted address (different owner): {address4}")

    logger.info("Determinism test PASSED!")


async def test_chain_configs():
    """Test that all chain configurations are valid."""
    logger.info("Testing chain configurations...")

    from intentkit.clients.privy import CHAIN_CONFIGS, ChainConfig

    required_networks = [
        "base-mainnet",
        "ethereum-mainnet",
        "polygon-mainnet",
        "arbitrum-mainnet",
        "optimism-mainnet",
    ]

    for network_id in required_networks:
        assert network_id in CHAIN_CONFIGS, f"Missing config for {network_id}"
        cfg = CHAIN_CONFIGS[network_id]
        assert isinstance(cfg, ChainConfig)
        assert cfg.chain_id > 0
        assert cfg.safe_tx_service_url.startswith("https://")
        assert cfg.allowance_module_address.startswith("0x")
        logger.info(f"  {network_id}: chain_id={cfg.chain_id}, usdc={cfg.usdc_address}")

    logger.info(f"All {len(required_networks)} required networks configured!")
    logger.info("Chain config test PASSED!")


async def test_wallet_provider_interface():
    """Test the WalletProvider abstract interface."""
    logger.info("Testing WalletProvider interface...")

    from intentkit.clients.privy import SafeWalletProvider, WalletProvider

    # Verify SafeWalletProvider implements WalletProvider
    assert issubclass(SafeWalletProvider, WalletProvider)

    # Check required methods exist
    required_methods = [
        "get_address",
        "execute_transaction",
        "transfer_erc20",
        "get_balance",
        "get_erc20_balance",
    ]

    for method in required_methods:
        assert hasattr(SafeWalletProvider, method), f"Missing method: {method}"

    logger.info("WalletProvider interface test PASSED!")


async def test_get_wallet_provider():
    """Test restoring a wallet provider from stored data."""
    logger.info("Testing get_wallet_provider...")

    from intentkit.clients.privy import SafeWalletProvider, get_wallet_provider

    wallet_data = {
        "privy_wallet_id": "test_wallet_id",
        "privy_wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE21",
        "smart_wallet_address": "0x1234567890123456789012345678901234567890",
        "network_id": "base-mainnet",
    }

    provider = get_wallet_provider(wallet_data)

    assert isinstance(provider, SafeWalletProvider)
    assert provider.privy_wallet_id == "test_wallet_id"
    assert provider.safe_address == "0x1234567890123456789012345678901234567890"

    # Test get_address
    address = await provider.get_address()
    assert address == "0x1234567890123456789012345678901234567890"

    logger.info("get_wallet_provider test PASSED!")


async def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("Starting Privy + Safe wallet integration tests")
    logger.info("=" * 60)

    try:
        await test_chain_configs()
        await test_address_prediction_determinism()
        await test_wallet_provider_interface()
        await test_get_wallet_provider()
        await test_wallet_creation_flow()

        logger.info("=" * 60)
        logger.info("All tests PASSED!")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
