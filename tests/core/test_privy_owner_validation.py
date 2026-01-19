from datetime import datetime
from unittest.mock import AsyncMock

import pytest

import intentkit.core.agent as agent_module
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData
from intentkit.utils.error import IntentKitAPIError


@pytest.mark.asyncio
async def test_process_agent_wallet_privy_requires_privy_did_owner(monkeypatch):
    now = datetime.now()
    agent = Agent(  # pyright: ignore[reportCallIssue]
        id="agent-safe-1",
        name="Test Agent",
        description="A test agent",
        model="gpt-4o",
        deployed_at=now,
        updated_at=now,
        created_at=now,
        owner="user_1",
        skills={},
        prompt="You are a helper.",
        temperature=0.7,
        visibility=0,
        public_info_updated_at=now,
        wallet_provider="safe",
        weekly_spending_limit=200.0,
        network_id="base-mainnet",
    )

    monkeypatch.setattr(
        agent_module.AgentData,
        "get",
        AsyncMock(
            side_effect=lambda _id: AgentData(  # pyright: ignore[reportCallIssue]
                id=_id,
                created_at=now,
                updated_at=now,
            )
        ),
    )

    with pytest.raises(IntentKitAPIError) as exc_info:
        await agent_module.process_agent_wallet(agent, old_wallet_provider="none")

    assert exc_info.value.key == "PrivyUserIdInvalid"
