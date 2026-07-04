import pytest

from intentkit.models.agent import Agent


@pytest.mark.asyncio
async def test_agent_get_json_schema_includes_tool_catalog():
    """Agent.get_json_schema exposes the toolset catalog from schema.json files.

    ``tools`` is a flat list of tool names; the per-category catalog (titles,
    descriptions, tool maps) is attached as the ``x-catalog`` extension so UIs
    can render a picker.
    """
    schema = await Agent.get_json_schema()

    tools_property = schema["properties"]["tools"]
    catalog = tools_property["x-catalog"]

    # erc20 should be present since it has a schema.json
    assert "erc20" in catalog
    erc20_tools = catalog["erc20"]["tools"]
    assert "erc20_get_balance" in erc20_tools
    assert "erc20_transfer" in erc20_tools
