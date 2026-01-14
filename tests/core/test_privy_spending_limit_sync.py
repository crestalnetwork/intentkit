import json
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

import intentkit.clients.privy as privy_module
import intentkit.core.agent as agent_module
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData


@pytest.mark.asyncio
async def test_process_agent_wallet_syncs_privy_limit_when_changed(monkeypatch):
    agent = Agent(  # pyright: ignore[reportCallIssue]
        id="agent-123",
        name="Test Agent",
        description="A test agent",
        model="gpt-4o",
        deployed_at=datetime.now(),
        updated_at=datetime.now(),
        created_at=datetime.now(),
        owner="user_1",
        skills={},
        prompt="You are a helper.",
        temperature=0.7,
        visibility=0,
        public_info_updated_at=datetime.now(),
        wallet_provider="privy",
        weekly_spending_limit=200.0,
        network_id="base-mainnet",
    )

    now = datetime.now()
    existing_agent_data = AgentData(
        id=agent.id,
        evm_wallet_address="0xsafe",
        privy_wallet_data=json.dumps(
            {
                "privy_wallet_id": "privy-wallet-1",
                "privy_wallet_address": "0xprivy",
                "smart_wallet_address": "0xsafe",
                "network_id": "base-mainnet",
            }
        ),
        created_at=now,
        updated_at=now,
    )

    updated_agent_data = AgentData(
        id=agent.id,
        evm_wallet_address="0xsafe",
        privy_wallet_data=json.dumps({"updated": True}),
        created_at=now,
        updated_at=now,
    )

    monkeypatch.setattr(
        agent_module.AgentData, "get", AsyncMock(return_value=existing_agent_data)
    )
    patch_mock = AsyncMock(return_value=updated_agent_data)
    monkeypatch.setattr(agent_module.AgentData, "patch", patch_mock)

    create_mock = AsyncMock(
        return_value={
            "privy_wallet_id": "privy-wallet-1",
            "privy_wallet_address": "0xprivy",
            "smart_wallet_address": "0xsafe",
            "provider": "safe",
            "network_id": "base-mainnet",
            "chain_id": 8453,
            "salt_nonce": 1,
            "deployment_info": {},
        }
    )
    monkeypatch.setattr(privy_module, "create_privy_safe_wallet", create_mock)

    result = await agent_module.process_agent_wallet(
        agent,
        old_wallet_provider="privy",
        old_weekly_spending_limit=100.0,
    )

    create_mock.assert_awaited_once()
    _, kwargs = create_mock.call_args
    assert kwargs["existing_privy_wallet_id"] == "privy-wallet-1"
    assert kwargs["existing_privy_wallet_address"] == "0xprivy"
    assert kwargs["weekly_spending_limit_usdc"] == 200.0

    patch_mock.assert_awaited_once()
    assert result == updated_agent_data


@pytest.mark.asyncio
async def test_process_agent_wallet_disables_privy_limit_when_set_to_none(monkeypatch):
    agent = Agent(  # pyright: ignore[reportCallIssue]
        id="agent-123",
        name="Test Agent",
        description="A test agent",
        model="gpt-4o",
        deployed_at=datetime.now(),
        updated_at=datetime.now(),
        created_at=datetime.now(),
        owner="user_1",
        skills={},
        prompt="You are a helper.",
        temperature=0.7,
        visibility=0,
        public_info_updated_at=datetime.now(),
        wallet_provider="privy",
        weekly_spending_limit=None,
        network_id="base-mainnet",
    )

    now = datetime.now()
    existing_agent_data = AgentData(
        id=agent.id,
        evm_wallet_address="0xsafe",
        privy_wallet_data=json.dumps(
            {
                "privy_wallet_id": "privy-wallet-1",
                "privy_wallet_address": "0xprivy",
                "smart_wallet_address": "0xsafe",
                "network_id": "base-mainnet",
            }
        ),
        created_at=now,
        updated_at=now,
    )

    monkeypatch.setattr(
        agent_module.AgentData, "get", AsyncMock(return_value=existing_agent_data)
    )
    monkeypatch.setattr(
        agent_module.AgentData, "patch", AsyncMock(return_value=existing_agent_data)
    )

    create_mock = AsyncMock(
        return_value={
            "privy_wallet_id": "privy-wallet-1",
            "privy_wallet_address": "0xprivy",
            "smart_wallet_address": "0xsafe",
            "provider": "safe",
            "network_id": "base-mainnet",
            "chain_id": 8453,
            "salt_nonce": 1,
            "deployment_info": {},
        }
    )
    monkeypatch.setattr(privy_module, "create_privy_safe_wallet", create_mock)

    await agent_module.process_agent_wallet(
        agent,
        old_wallet_provider="privy",
        old_weekly_spending_limit=100.0,
    )

    create_mock.assert_awaited_once()
    _, kwargs = create_mock.call_args
    assert kwargs["weekly_spending_limit_usdc"] == 0.0
