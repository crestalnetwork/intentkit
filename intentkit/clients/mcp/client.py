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
async def _session_from_streams(
    transport_streams: tuple[Any, ...],
) -> AsyncGenerator[ClientSession]:
    read_stream, write_stream = transport_streams[0], transport_streams[1]
    async with ClientSession(
        read_stream, write_stream, client_info=_CLIENT_INFO
    ) as session:
        yield session


@asynccontextmanager
async def _connect(
    url: str, transport: str, headers: dict[str, str]
) -> AsyncGenerator[ClientSession]:
    """Connect to an MCP server and yield an initialized session."""
    if transport == "sse":
        async with sse_client(url, headers=headers) as transport_streams:
            async with _session_from_streams(transport_streams) as session:
                yield session
    elif transport == "streamable_http":
        # streamable_http_client only manages the lifecycle of a client it
        # creates itself; a caller-provided one (needed for headers) must be
        # closed by us or its connection pool leaks on every call.
        async with httpx.AsyncClient(headers=headers, timeout=60) as http_client:
            async with streamable_http_client(
                url, http_client=http_client
            ) as transport_streams:
                async with _session_from_streams(transport_streams) as session:
                    yield session
    else:
        raise ValueError(f"Unknown transport: {transport}")


async def list_mcp_tools_at(
    url: str, transport: str, headers: dict[str, str]
) -> list[McpToolInfo]:
    """Connect to an MCP endpoint by URL and list available tools."""
    async with _connect(url, transport, headers) as session:
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


async def list_mcp_tools(
    server_def: McpServerDef, api_key: str | None
) -> list[McpToolInfo]:
    """Connect to a registry-defined MCP server and list available tools."""
    headers = _build_headers(server_def, api_key)
    return await list_mcp_tools_at(server_def.url, server_def.transport, headers)


async def call_mcp_tool_at(
    url: str,
    transport: str,
    headers: dict[str, str],
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    """Connect to an MCP endpoint by URL and invoke a tool."""
    async with _connect(url, transport, headers) as session:
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


async def call_mcp_tool(
    server_def: McpServerDef,
    api_key: str | None,
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    """Connect to a registry-defined MCP server and invoke a tool."""
    headers = _build_headers(server_def, api_key)
    return await call_mcp_tool_at(
        server_def.url, server_def.transport, headers, tool_name, arguments
    )


class McpToolError(Exception):
    """Error raised when an MCP tool call fails."""
