from decimal import Decimal
from unittest.mock import MagicMock

import pytest

import intentkit.core.asset as asset_module
from intentkit.core.asset import NATION_ADDRESS, USDC_ADDRESSES


@pytest.mark.asyncio
async def test_asset_deduplication_usdc(monkeypatch):
    """USDC token_address should not create duplicate USDC entries."""
    web3_client = MagicMock()

    agent = MagicMock()
    agent.id = "test-agent"
    agent.network_id = "base-mainnet"
    agent.ticker = "USDC"
    agent.token_address = USDC_ADDRESSES["base-mainnet"]

    agent_data = MagicMock()
    agent_data.agent_id = "test-agent"
    agent_data.evm_wallet_address = "0x1234567890123456789012345678901234567890"

    async def mock_get_eth_balance(client, address):
        return Decimal("1.0")

    async def mock_get_token_balance(client, wallet, token_addr):
        return Decimal("100.0")

    monkeypatch.setattr(asset_module, "_get_eth_balance", mock_get_eth_balance)
    monkeypatch.setattr(asset_module, "_get_token_balance", mock_get_token_balance)

    assets = await asset_module._build_assets_list(agent, agent_data, web3_client)

    assert len(assets) == 3
    symbols = [asset.symbol for asset in assets]
    assert symbols.count("USDC") == 1
    assert {asset.symbol for asset in assets} == {"ETH", "USDC", "NATION"}


@pytest.mark.asyncio
async def test_asset_deduplication_nation(monkeypatch):
    """NATION token_address should not create duplicate NATION entries."""
    web3_client = MagicMock()

    agent = MagicMock()
    agent.id = "test-agent"
    agent.network_id = "base-mainnet"
    agent.ticker = "NATION"
    agent.token_address = NATION_ADDRESS

    agent_data = MagicMock()
    agent_data.agent_id = "test-agent"
    agent_data.evm_wallet_address = "0x1234567890123456789012345678901234567890"

    async def mock_get_eth_balance(client, address):
        return Decimal("1.0")

    async def mock_get_token_balance(client, wallet, token_addr):
        return Decimal("1000.0")

    monkeypatch.setattr(asset_module, "_get_eth_balance", mock_get_eth_balance)
    monkeypatch.setattr(asset_module, "_get_token_balance", mock_get_token_balance)

    assets = await asset_module._build_assets_list(agent, agent_data, web3_client)

    assert len(assets) == 3
    symbols = [asset.symbol for asset in assets]
    assert symbols.count("NATION") == 1
    assert {asset.symbol for asset in assets} == {"ETH", "USDC", "NATION"}


@pytest.mark.asyncio
async def test_asset_no_deduplication_custom_token(monkeypatch):
    """Custom tokens with different addresses should be added normally."""
    web3_client = MagicMock()

    agent = MagicMock()
    agent.id = "test-agent"
    agent.network_id = "base-mainnet"
    agent.ticker = "CUSTOM"
    agent.token_address = "0x9999999999999999999999999999999999999999"

    agent_data = MagicMock()
    agent_data.agent_id = "test-agent"
    agent_data.evm_wallet_address = "0x1234567890123456789012345678901234567890"

    async def mock_get_eth_balance(client, address):
        return Decimal("1.0")

    async def mock_get_token_balance(client, wallet, token_addr):
        return Decimal("500.0")

    monkeypatch.setattr(asset_module, "_get_eth_balance", mock_get_eth_balance)
    monkeypatch.setattr(asset_module, "_get_token_balance", mock_get_token_balance)

    assets = await asset_module._build_assets_list(agent, agent_data, web3_client)

    assert len(assets) == 4
    symbols = [asset.symbol for asset in assets]
    assert {"ETH", "USDC", "NATION", "CUSTOM"}.issubset(set(symbols))


@pytest.mark.asyncio
async def test_case_insensitive_deduplication(monkeypatch):
    """Deduplication must work with case-insensitive addresses."""
    web3_client = MagicMock()

    agent = MagicMock()
    agent.id = "test-agent"
    agent.network_id = "base-mainnet"
    agent.ticker = "USDC"
    agent.token_address = USDC_ADDRESSES["base-mainnet"].upper()

    agent_data = MagicMock()
    agent_data.agent_id = "test-agent"
    agent_data.evm_wallet_address = "0x1234567890123456789012345678901234567890"

    async def mock_get_eth_balance(client, address):
        return Decimal("1.0")

    async def mock_get_token_balance(client, wallet, token_addr):
        return Decimal("100.0")

    monkeypatch.setattr(asset_module, "_get_eth_balance", mock_get_eth_balance)
    monkeypatch.setattr(asset_module, "_get_token_balance", mock_get_token_balance)

    assets = await asset_module._build_assets_list(agent, agent_data, web3_client)

    assert len(assets) == 3
    symbols = [asset.symbol for asset in assets]
    assert symbols.count("USDC") == 1
    assert {asset.symbol for asset in assets} == {"ETH", "USDC", "NATION"}
