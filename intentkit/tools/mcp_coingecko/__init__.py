"""CoinGecko MCP tools — crypto market data, prices, and analytics."""

from intentkit.tools.mcp.wrapper import create_mcp_category

_module = create_mcp_category("mcp_coingecko")

get_tools = _module.get_tools
available = _module.available
