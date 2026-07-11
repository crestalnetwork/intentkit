"""Factory that creates standard IntentKit toolset interfaces for MCP servers."""

import logging
import time
from typing import Any

from intentkit.clients.mcp.client import list_mcp_tools
from intentkit.clients.mcp.registry import MCP_SERVERS, McpServerDef
from intentkit.config.config import config as system_config
from intentkit.tools.mcp.tool import McpToolTool, create_mcp_tool
from intentkit.tools.meta import ToolMeta, ToolsetMeta

logger = logging.getLogger(__name__)

# In-memory cache: {(server_name, api_key): (tool_instances, timestamp)}.
# Keyed by the resolved API key too, because a server may expose a different
# tool set per key — sharing one entry across keys would poison discovery.
_cache: dict[tuple[str, str | None], tuple[dict[str, McpToolTool], float]] = {}
_CACHE_TTL = 3600  # 1 hour


def _resolve_system_api_key(server_def: McpServerDef) -> str | None:
    """Get the system-level API key for an MCP server."""
    if server_def.api_key_config_attr:
        return getattr(system_config, server_def.api_key_config_attr, None)
    return None


async def _get_mcp_tool_instances(
    server_def: McpServerDef,
) -> dict[str, McpToolTool]:
    """Get pre-built tool instances for an MCP server, with caching."""
    api_key = _resolve_system_api_key(server_def)
    cache_key = (server_def.name, api_key)

    now = time.time()
    cached = _cache.get(cache_key)
    if cached:
        instances, ts = cached
        if now - ts < _CACHE_TTL:
            return instances

    try:
        tool_infos = await list_mcp_tools(server_def, api_key)
        instances = {
            f"{server_def.name}_{t.name}": create_mcp_tool(
                server_def, t.name, t.description, t.input_schema
            )
            for t in tool_infos
        }
        _cache[cache_key] = (instances, now)
        logger.info(
            "Discovered %d tools from MCP server '%s'",
            len(instances),
            server_def.name,
        )
        return instances
    except Exception:
        logger.warning(
            "Failed to discover tools from MCP server '%s'",
            server_def.name,
            exc_info=True,
        )
        if cached:
            return cached[0]
        return {}


class McpCategoryModule:
    """Provides the standard toolset interface for an MCP server."""

    server_name: str
    toolset: ToolsetMeta
    _server_def: McpServerDef

    def __init__(self, server_name: str):
        self.server_name = server_name
        self._server_def = MCP_SERVERS[server_name]
        # Remote MCP servers own their (changing) tool list, so the catalog
        # carries a single fixed entry for the whole server instead of a
        # per-tool snapshot that could go stale.
        self.toolset = ToolsetMeta(
            title=self._server_def.display_name,
            description=self._server_def.description,
            tags=list(self._server_def.tags),
            web3=self._server_def.web3,
            wallet=self._server_def.wallet,
            icon=self._server_def.icon,
            tools={
                self._server_def.name: ToolMeta(
                    title=f"All {self._server_def.display_name} Tools",
                    description=(
                        f"Expose every tool offered by the "
                        f"{self._server_def.display_name} MCP server. The exact "
                        "tools are discovered live from the server at runtime."
                    ),
                )
            },
        )

    async def get_tools(
        self,
        tool_names: list[str],
        **_: Any,
    ) -> list[McpToolTool]:
        """Expose the server's tools when the server name is enabled.

        Remote MCP servers own their (changing) tool list, so we never
        snapshot or toggle individual tools. The agent's tools list carries a
        single entry for the whole server, keyed by the server name; when
        present, every tool discovered live from the server is exposed. This
        can't drift when the server changes its tools.
        """
        if self._server_def.name not in tool_names:
            return []

        instances = await _get_mcp_tool_instances(self._server_def)
        return list(instances.values())

    def available(self) -> bool:
        """Check if this MCP server is available.

        Returns True if no API key is required, or if a system-level key is configured.
        """
        if self._server_def.api_key_config_attr:
            return bool(_resolve_system_api_key(self._server_def))
        return True


def create_mcp_category(server_name: str) -> McpCategoryModule:
    """Create a toolset module for a registered MCP server."""
    if server_name not in MCP_SERVERS:
        raise ValueError(
            f"MCP server '{server_name}' not found in registry. "
            f"Available: {list(MCP_SERVERS.keys())}"
        )
    return McpCategoryModule(server_name)
