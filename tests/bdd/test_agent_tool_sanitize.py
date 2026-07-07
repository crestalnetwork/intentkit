import pytest

from intentkit.core.agent.management import create_agent, override_agent, patch_agent
from intentkit.models.agent import AgentCreate, AgentUpdate

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.bdd
async def test_override_agent_sanitizes_stale_tools():
    agent = AgentCreate(id="test-sanitize-1", name="Sanitize Test", model="gpt-4o-mini")
    await create_agent(agent)

    update = AgentUpdate(
        name="Sanitize Test",
        model="gpt-4o-mini",
        tools=["http_get", "deleted_tool", "nonexistent_cat_tool"],
    )
    result, _ = await override_agent("test-sanitize-1", update)
    assert result.tools is not None
    assert "deleted_tool" not in result.tools
    assert "nonexistent_cat_tool" not in result.tools
    assert "http_get" in result.tools


@pytest.mark.bdd
async def test_patch_agent_sanitizes_stale_tools():
    agent = AgentCreate(
        id="test-sanitize-2", name="Sanitize Patch", model="gpt-4o-mini"
    )
    await create_agent(agent)

    update = AgentUpdate(
        name="Sanitize Patch",
        model="gpt-4o-mini",
        tools=["http_get", "old_tool", "http_get"],
    )
    result, _ = await patch_agent("test-sanitize-2", update)
    assert result.tools is not None
    assert "old_tool" not in result.tools
    # Duplicates are collapsed to a single entry
    assert result.tools.count("http_get") == 1
