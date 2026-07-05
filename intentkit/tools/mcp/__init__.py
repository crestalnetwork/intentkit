"""Toolset wrappers that expose MCP servers as IntentKit tools.

Not a toolset category itself (no ``toolset`` meta); categories like
``mcp_coingecko`` build on this via ``create_mcp_category``. The underlying
MCP protocol client lives in ``intentkit.clients.mcp``.
"""

from intentkit.tools.mcp.wrapper import McpCategoryModule, create_mcp_category

__all__ = ["McpCategoryModule", "create_mcp_category"]
