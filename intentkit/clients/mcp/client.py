"""MCP HTTP client for connecting to remote MCP servers."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import Implementation, TextContent

from intentkit.clients.mcp.registry import McpServerDef

logger = logging.getLogger(__name__)


@dataclass
class McpToolInfo:
    """Information about a tool discovered from an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]


def _build_headers(server_def: McpServerDef, api_key: str | None) -> dict[str, str]:
    """Build HTTP headers for MCP server connection."""
    headers: dict[str, str] = {}
    if api_key and server_def.api_key_header:
        if server_def.api_key_prefix:
            headers[server_def.api_key_header] = (
                f"{server_def.api_key_prefix} {api_key}"
            )
        else:
            headers[server_def.api_key_header] = api_key
    return headers


_CLIENT_INFO = Implementation(name="claude-code", version="1.0.12")


@asynccontextmanager
async def _connect(
    server_def: McpServerDef, headers: dict[str, str]
) -> AsyncGenerator[ClientSession]:
    """Connect to an MCP server and yield an initialized session."""
    if server_def.transport == "sse":
        cm = sse_client(server_def.url, headers=headers)
    elif server_def.transport == "streamable_http":
        http_client = httpx.AsyncClient(headers=headers, timeout=60)
        cm = streamable_http_client(server_def.url, http_client=http_client)
    else:
        raise ValueError(f"Unknown transport: {server_def.transport}")

    async with cm as transport:
        read_stream, write_stream = transport[0], transport[1]
        async with ClientSession(
            read_stream, write_stream, client_info=_CLIENT_INFO
        ) as session:
            yield session


async def list_mcp_tools(
    server_def: McpServerDef, api_key: str | None
) -> list[McpToolInfo]:
    """Connect to an MCP server and list available tools."""
    headers = _build_headers(server_def, api_key)

    async with _connect(server_def, headers) as session:
        await session.initialize()
        result = await session.list_tools()
        return [
            McpToolInfo(
                name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema if tool.inputSchema else {},
            )
            for tool in result.tools
        ]


async def call_mcp_tool(
    server_def: McpServerDef,
    api_key: str | None,
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    """Connect to an MCP server and invoke a tool."""
    headers = _build_headers(server_def, api_key)

    async with _connect(server_def, headers) as session:
        await session.initialize()
        result = await session.call_tool(tool_name, arguments)

        if result.isError:
            error_text = "\n".join(
                c.text for c in result.content if isinstance(c, TextContent)
            )
            raise McpToolError(
                f"MCP tool '{tool_name}' returned error: {error_text or 'unknown error'}"
            )

        parts: list[str] = []
        for content in result.content:
            if isinstance(content, TextContent):
                parts.append(content.text)
            else:
                parts.append(str(content))
        return "\n".join(parts)


class McpToolError(Exception):
    """Error raised when an MCP tool call fails."""
