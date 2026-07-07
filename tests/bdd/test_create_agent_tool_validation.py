import pytest

from intentkit.core.agent.management import create_agent
from intentkit.models.agent import AgentCreate
from intentkit.utils.error import IntentKitAPIError

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.bdd
async def test_create_agent_rejects_unknown_tool_name():
    agent = AgentCreate(
        id="test-tool-val-1",
        name="Tool Test",
        model="gpt-4o-mini",
        tools=["nonexistent_tool"],
    )
    with pytest.raises(IntentKitAPIError, match="nonexistent_tool"):
        await create_agent(agent)


@pytest.mark.bdd
async def test_create_agent_rejects_fake_tool_in_known_category():
    # Name uses a real category prefix ("http_") but is not a real tool.
    agent = AgentCreate(
        id="test-tool-val-2",
        name="Tool Test",
        model="gpt-4o-mini",
        tools=["http_fake_tool"],
    )
    with pytest.raises(IntentKitAPIError, match="http_fake_tool"):
        await create_agent(agent)


@pytest.mark.bdd
async def test_create_agent_accepts_valid_tools():
    agent = AgentCreate(
        id="test-tool-val-3",
        name="Tool Test Valid",
        model="gpt-4o-mini",
        tools=["http_get"],
    )
    created, _ = await create_agent(agent)
    assert created.tools is not None
    assert "http_get" in created.tools
