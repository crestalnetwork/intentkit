from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import intentkit.core.asset as asset_module
from intentkit.core.asset import AgentAssets, Asset
from intentkit.utils.error import IntentKitAPIError


@pytest.mark.asyncio
async def test_agent_asset_missing_agent(monkeypatch):
    class DummyAgent:
        @classmethod
        async def get(cls, agent_id: str):
            return None

    class DummyAgentData:
        @classmethod
        async def get(cls, agent_id: str):
            return SimpleNamespace(evm_wallet_address=None)

    monkeypatch.setattr(asset_module, "Agent", DummyAgent)
    monkeypatch.setattr(asset_module, "AgentData", DummyAgentData)

    with pytest.raises(IntentKitAPIError) as exc:
        await asset_module.agent_asset("missing")

    assert exc.value.status_code == 404
    assert exc.value.key == "AgentNotFound"


@pytest.mark.asyncio
async def test_agent_asset_no_wallet(monkeypatch):
    agent = SimpleNamespace(network_id="base-mainnet", ticker=None, token_address=None)

    class DummyAgent:
        @classmethod
        async def get(cls, agent_id: str):
            return agent

    class DummyAgentData:
        @classmethod
        async def get(cls, agent_id: str):
            return SimpleNamespace(evm_wallet_address=None)

    monkeypatch.setattr(asset_module, "Agent", DummyAgent)
    monkeypatch.setattr(asset_module, "AgentData", DummyAgentData)

    result = await asset_module.agent_asset("agent-id")

    assert isinstance(result, AgentAssets)
    assert result.net_worth == "0"
    assert result.tokens == []


@pytest.mark.asyncio
async def test_agent_asset_success(monkeypatch):
    agent = SimpleNamespace(
        network_id="base-mainnet", ticker="WOW", token_address="0xabc"
    )

    class DummyAgent:
        @classmethod
        async def get(cls, agent_id: str):
            return agent

    class DummyAgentData:
        @classmethod
        async def get(cls, agent_id: str):
            return SimpleNamespace(evm_wallet_address="0x123")

    async def mock_build_assets_list(agent_obj, agent_data_obj, web3_client):
        return [Asset(symbol="ETH", balance=Decimal("1"))]

    async def mock_get_wallet_net_worth(wallet):
        return "123.45"

    monkeypatch.setattr(asset_module, "Agent", DummyAgent)
    monkeypatch.setattr(asset_module, "AgentData", DummyAgentData)
    monkeypatch.setattr(asset_module, "get_web3_client", lambda network: MagicMock())
    monkeypatch.setattr(asset_module, "_build_assets_list", mock_build_assets_list)
    monkeypatch.setattr(
        asset_module, "_get_wallet_net_worth", mock_get_wallet_net_worth
    )

    result = await asset_module.agent_asset("agent-id")

    assert isinstance(result, AgentAssets)
    assert result.net_worth == "123.45"
    assert result.tokens == [Asset(symbol="ETH", balance=Decimal("1"))]


@pytest.mark.asyncio
async def test_agent_asset_missing_network(monkeypatch):
    agent = SimpleNamespace(network_id=None, ticker=None, token_address=None)

    class DummyAgent:
        @classmethod
        async def get(cls, agent_id: str):
            return agent

    class DummyAgentData:
        @classmethod
        async def get(cls, agent_id: str):
            return SimpleNamespace(evm_wallet_address="0x123")

    monkeypatch.setattr(asset_module, "Agent", DummyAgent)
    monkeypatch.setattr(asset_module, "AgentData", DummyAgentData)

    result = await asset_module.agent_asset("agent-id")

    assert result.net_worth == "0"
    assert result.tokens == []
