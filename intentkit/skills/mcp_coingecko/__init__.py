"""CoinGecko MCP skills — crypto market data, prices, and analytics."""

from intentkit.clients.mcp.wrapper import create_mcp_category

_module = create_mcp_category("mcp_coingecko")

get_skills = _module.get_skills
available = _module.available
Config = _module.Config
