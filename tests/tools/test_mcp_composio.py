"""Tests for intentkit.tools.mcp.composio (session MCP tool wrapping)."""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.tools.base import ToolException

from intentkit.clients.mcp.client import McpToolError, McpToolInfo
from intentkit.tools.mcp.composio import ComposioMcpTool, build_composio_mcp_tools

MODULE = "intentkit.tools.mcp.composio"


@pytest.fixture(autouse=True)
def _configured():
    with patch("intentkit.clients.composio.config.composio_api_key", "test-key"):
        yield


class TestBuildComposioMcpTools:
    @pytest.mark.asyncio
    async def test_wraps_discovered_tools(self):
        infos = [
            McpToolInfo(
                name="COMPOSIO_SEARCH_TOOLS",
                description="Search tools",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "q"},
                    },
                    "required": ["query"],
                },
            ),
            McpToolInfo(
                name="COMPOSIO_EXECUTE_TOOL",
                description="",
                input_schema={},
            ),
        ]
        with patch(
            f"{MODULE}.list_mcp_tools_at",
            new_callable=AsyncMock,
            return_value=infos,
        ) as mock_list:
            tools = await build_composio_mcp_tools("https://mcp/x")

        mock_list.assert_awaited_once_with(
            "https://mcp/x", "streamable_http", {"x-api-key": "test-key"}
        )
        assert [t.name for t in tools] == [
            "COMPOSIO_SEARCH_TOOLS",
            "COMPOSIO_EXECUTE_TOOL",
        ]
        assert all(isinstance(t, ComposioMcpTool) for t in tools)
        assert tools[0].mcp_url == "https://mcp/x"
        assert tools[0].description == "Search tools"
        # Empty descriptions get a fallback so the LLM sees something
        assert "COMPOSIO_EXECUTE_TOOL" in tools[1].description
        # args schema reflects the MCP inputSchema
        assert "query" in tools[0].get_input_jsonschema()["properties"]


class TestComposioMcpToolRun:
    def _tool(self) -> ComposioMcpTool:
        return ComposioMcpTool(
            name="COMPOSIO_SEARCH_TOOLS",
            description="d",
            mcp_url="https://mcp/x",
            mcp_tool_name="COMPOSIO_SEARCH_TOOLS",
        )

    @pytest.mark.asyncio
    async def test_arun_calls_endpoint(self):
        with patch(
            f"{MODULE}.call_mcp_tool_at",
            new_callable=AsyncMock,
            return_value="result",
        ) as mock_call:
            result = await self._tool()._arun(query="gmail")

        assert result == "result"
        mock_call.assert_awaited_once_with(
            "https://mcp/x",
            "streamable_http",
            {"x-api-key": "test-key"},
            "COMPOSIO_SEARCH_TOOLS",
            {"query": "gmail"},
        )

    @pytest.mark.asyncio
    async def test_mcp_error_becomes_tool_exception(self):
        with patch(
            f"{MODULE}.call_mcp_tool_at",
            new_callable=AsyncMock,
            side_effect=McpToolError("remote error"),
        ):
            with pytest.raises(ToolException, match="remote error"):
                await self._tool()._arun()

    @pytest.mark.asyncio
    async def test_other_error_becomes_tool_exception(self):
        with patch(
            f"{MODULE}.call_mcp_tool_at",
            new_callable=AsyncMock,
            side_effect=ConnectionError("refused"),
        ):
            with pytest.raises(ToolException, match="COMPOSIO_SEARCH_TOOLS"):
                await self._tool()._arun()
