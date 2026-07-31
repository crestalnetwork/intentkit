"""Tests for intentkit.clients.mcp.client (SDK model -> McpToolInfo translation).

These deliberately build **real** ``mcp.types`` objects rather than mocks or
dicts. The rest of the MCP tests stub ``list_mcp_tools_at``/``call_mcp_tool_at``
at our own boundary, which leaves the translation below untested — and that is
exactly the layer an SDK field rename breaks. mcp 2.0.0 renamed ``inputSchema``
to ``input_schema`` and ``isError`` to ``is_error``; nothing here caught it.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from intentkit.clients.mcp.client import (
    McpToolError,
    call_mcp_tool_at,
    list_mcp_tools_at,
)

MODULE = "intentkit.clients.mcp.client"


def _session(*, tools=None, call_result=None):
    """A stand-in for ClientSession exposing only what the client calls."""
    session = AsyncMock()
    session.list_tools.return_value = ListToolsResult(tools=tools or [])
    if call_result is not None:
        session.call_tool.return_value = call_result
    return session


@asynccontextmanager
async def _yield(session):
    yield session


class TestListMcpToolsAt:
    @pytest.mark.asyncio
    async def test_translates_sdk_tools(self):
        schema = {
            "type": "object",
            "properties": {"symbol": {"type": "string"}},
            "required": ["symbol"],
        }
        session = _session(
            tools=[
                Tool(name="get_price", description="Get a price", input_schema=schema),
                Tool(name="no_description", input_schema={}),
            ]
        )
        with patch(f"{MODULE}._connect", return_value=_yield(session)):
            infos = await list_mcp_tools_at("https://mcp/x", "sse", {})

        session.initialize.assert_awaited_once()
        assert [i.name for i in infos] == ["get_price", "no_description"]
        assert infos[0].description == "Get a price"
        assert infos[0].input_schema == schema
        # A missing description and an empty schema normalise, never leak None.
        assert infos[1].description == ""
        assert infos[1].input_schema == {}


class TestCallMcpToolAt:
    @pytest.mark.asyncio
    async def test_joins_text_content(self):
        session = _session(
            call_result=CallToolResult(
                content=[
                    TextContent(type="text", text="first"),
                    TextContent(type="text", text="second"),
                ]
            )
        )
        with patch(f"{MODULE}._connect", return_value=_yield(session)):
            out = await call_mcp_tool_at("https://mcp/x", "sse", {}, "t", {"a": 1})

        assert out == "first\nsecond"
        session.call_tool.assert_awaited_once_with("t", {"a": 1})

    @pytest.mark.asyncio
    async def test_raises_on_error_result(self):
        session = _session(
            call_result=CallToolResult(
                content=[TextContent(type="text", text="rate limited")],
                is_error=True,
            )
        )
        with patch(f"{MODULE}._connect", return_value=_yield(session)):
            with pytest.raises(McpToolError, match="rate limited"):
                await call_mcp_tool_at("https://mcp/x", "sse", {}, "t", {})

    @pytest.mark.asyncio
    async def test_error_result_without_text_still_raises(self):
        session = _session(call_result=CallToolResult(content=[], is_error=True))
        with patch(f"{MODULE}._connect", return_value=_yield(session)):
            with pytest.raises(McpToolError, match="unknown error"):
                await call_mcp_tool_at("https://mcp/x", "sse", {}, "t", {})
