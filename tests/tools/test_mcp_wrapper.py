"""Coarse enablement behavior of the MCP toolset wrapper.

An MCP category carries a single entry in the agent's tools list, keyed by
the server name; when present, every live-discovered tool is exposed. There
are no per-tool entries, so a remote tool-list change can't leave the config
stale. These tests mock discovery, so they never touch the network.
"""

from unittest.mock import AsyncMock, patch

import pytest

from intentkit.tools.mcp.wrapper import McpCategoryModule

_FAKE_INSTANCES = {
    "mcp_coingecko_execute": object(),
    "mcp_coingecko_search_docs": object(),
}


@pytest.mark.asyncio
async def test_server_name_exposes_all_discovered_tools():
    module = McpCategoryModule("mcp_coingecko")
    with patch(
        "intentkit.tools.mcp.wrapper._get_mcp_tool_instances",
        new=AsyncMock(return_value=dict(_FAKE_INSTANCES)),
    ):
        tools = await module.get_tools(["mcp_coingecko"])

    assert len(tools) == len(_FAKE_INSTANCES)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_names",
    [
        [],  # server not selected at all
        ["other_category_tool"],  # unrelated names only
        ["mcp_coingecko_get_price"],  # stale per-tool snapshot key
    ],
)
async def test_absent_server_name_exposes_nothing(tool_names):
    """Without the server-name entry no tools are exposed — including configs
    still keyed by individual tool names, which must not silently expose the
    whole server (and must not trigger any network discovery)."""
    module = McpCategoryModule("mcp_coingecko")
    with patch(
        "intentkit.tools.mcp.wrapper._get_mcp_tool_instances",
        new=AsyncMock(return_value=dict(_FAKE_INSTANCES)),
    ) as mock_discover:
        tools = await module.get_tools(tool_names)

    assert tools == []
    mock_discover.assert_not_called()
