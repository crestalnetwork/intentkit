from contextlib import asynccontextmanager
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import intentkit.core.asset as asset_module
from intentkit.core.asset import AgentAssets, Asset
from intentkit.utils.error import IntentKitAPIError


# Mock get_session globally for this module or per test
@asynccontextmanager
async def mock_session_ctx():
    session = MagicMock()
    # Ensure commit is async
    session.commit = MagicMock()

    async def async_commit():
        pass

    session.commit.side_effect = async_commit

    # Ensure execute is async
    session.execute = MagicMock()

    async def async_execute(*args, **kwargs):
        pass

    session.execute.side_effect = async_execute

    yield session


@pytest.mark.asyncio
async def test_agent_asset_missing_agent(monkeypatch):
    async def mock_get_agent(agent_id):
        return None

    # We also mock AgentData just in case, though get_agent failure exits early
    monkeypatch.setattr(asset_module, "get_agent", mock_get_agent)
    # Patch get_session to avoid DB init check
    monkeypatch.setattr(asset_module, "get_session", mock_session_ctx)
    # Patch get_redis to return None to avoid redis connection
    monkeypatch.setattr(asset_module, "get_redis", lambda: None)

    with pytest.raises(IntentKitAPIError) as exc:
        await asset_module.agent_asset("missing")

    assert exc.value.status_code == 404
    assert exc.value.key == "AgentNotFound"


@pytest.mark.asyncio
async def test_agent_asset_no_wallet(monkeypatch):
    agent = SimpleNamespace(
        network_id="base-mainnet", ticker=None, token_address=None, id="agent-id"
    )

    async def mock_get_agent(agent_id):
        return agent

    class DummyAgentData:
        @classmethod
        async def get(cls, agent_id: str):
            return SimpleNamespace(evm_wallet_address=None)

    monkeypatch.setattr(asset_module, "get_agent", mock_get_agent)
    monkeypatch.setattr(asset_module, "AgentData", DummyAgentData)
    monkeypatch.setattr(asset_module, "get_session", mock_session_ctx)
    monkeypatch.setattr(asset_module, "get_redis", lambda: None)

    result = await asset_module.agent_asset("agent-id")

    assert isinstance(result, AgentAssets)
    assert result.net_worth == "0"
    assert result.tokens == []


@pytest.mark.asyncio
async def test_agent_asset_success(monkeypatch):
    agent = SimpleNamespace(
        network_id="base-mainnet", ticker="WOW", token_address="0xabc", id="agent-id"
    )

    async def mock_get_agent(agent_id):
        return agent

    class DummyAgentData:
        @classmethod
        async def get(cls, agent_id: str):
            return SimpleNamespace(evm_wallet_address="0x123")

    async def mock_build_assets_list(agent_obj, agent_data_obj, web3_client):
        return [Asset(symbol="ETH", balance=Decimal("1"))]

    async def mock_get_wallet_net_worth(wallet, network_id):
        assert network_id == "base-mainnet"
        return "123.45"

    monkeypatch.setattr(asset_module, "get_agent", mock_get_agent)
    monkeypatch.setattr(asset_module, "AgentData", DummyAgentData)
    monkeypatch.setattr(asset_module, "get_web3_client", lambda network: MagicMock())
    monkeypatch.setattr(asset_module, "_build_assets_list", mock_build_assets_list)
    monkeypatch.setattr(
        asset_module, "_get_wallet_net_worth", mock_get_wallet_net_worth
    )
    monkeypatch.setattr(asset_module, "get_session", mock_session_ctx)
    monkeypatch.setattr(asset_module, "get_redis", lambda: None)

    result = await asset_module.agent_asset("agent-id")

    assert isinstance(result, AgentAssets)
    assert result.net_worth == "123.45"
    assert result.tokens == [Asset(symbol="ETH", balance=Decimal("1"))]


@pytest.mark.asyncio
async def test_agent_asset_missing_network(monkeypatch):
    agent = SimpleNamespace(
        network_id=None, ticker=None, token_address=None, id="agent-id"
    )

    async def mock_get_agent(agent_id):
        return agent

    class DummyAgentData:
        @classmethod
        async def get(cls, agent_id: str):
            return SimpleNamespace(evm_wallet_address="0x123")

    monkeypatch.setattr(asset_module, "get_agent", mock_get_agent)
    monkeypatch.setattr(asset_module, "AgentData", DummyAgentData)
    monkeypatch.setattr(asset_module, "get_session", mock_session_ctx)
    monkeypatch.setattr(asset_module, "get_redis", lambda: None)

    result = await asset_module.agent_asset("agent-id")

    assert result.net_worth == "0"
    assert result.tokens == []
