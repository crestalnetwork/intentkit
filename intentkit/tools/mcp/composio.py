"""Composio session MCP tools.

Wraps the tools exposed by a Composio Tool Router session's hosted MCP
endpoint as IntentKit tools. Unlike the registry-based MCP toolsets
(``intentkit.tools.mcp.wrapper``), the endpoint URL here is dynamic — one
session per team, created when the lead executor is built — so each tool
carries its session URL instead of a registry key.
"""

import logging
from typing import Any

from langchain_core.tools.base import ToolException

from intentkit.clients.composio import get_composio_client
from intentkit.clients.mcp.client import (
    McpToolError,
    call_mcp_tool_at,
    list_mcp_tools_at,
)
from intentkit.tools.base import IntentKitTool
from intentkit.tools.mcp.tool import create_args_model

logger = logging.getLogger(__name__)

_TRANSPORT = "streamable_http"


class ComposioMcpTool(IntentKitTool):
    """One tool of a Composio session's MCP endpoint.

    The session URL is baked in at executor-build time; authentication
    headers are re-derived from system config on every call so no secret is
    stored on the tool instance.
    """

    category: str = "composio"

    mcp_url: str
    """The session's hosted MCP endpoint URL."""

    mcp_tool_name: str
    """Original tool name on the MCP server."""

    async def _arun(self, **kwargs: Any) -> str:
        headers = get_composio_client().mcp_headers
        try:
            return await call_mcp_tool_at(
                self.mcp_url, _TRANSPORT, headers, self.mcp_tool_name, kwargs
            )
        except McpToolError as e:
            raise ToolException(str(e)) from e
        except Exception as e:
            raise ToolException(
                f"Failed to call Composio tool '{self.mcp_tool_name}': {e}"
            ) from e


async def build_composio_mcp_tools(mcp_url: str) -> list[ComposioMcpTool]:
    """Discover the tools of a Composio session MCP endpoint and wrap them."""
    headers = get_composio_client().mcp_headers
    infos = await list_mcp_tools_at(mcp_url, _TRANSPORT, headers)
    tools: list[ComposioMcpTool] = []
    for info in infos:
        tools.append(
            ComposioMcpTool(
                name=info.name,
                description=info.description or f"Composio tool: {info.name}",
                args_schema=create_args_model(info.name, info.input_schema),
                mcp_url=mcp_url,
                mcp_tool_name=info.name,
            )
        )
    return tools
