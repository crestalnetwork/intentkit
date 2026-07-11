"""Registry of remote MCP servers to be wrapped as IntentKit toolsets."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class McpServerDef:
    """Definition of a remote MCP server."""

    name: str
    """Toolset name, e.g. 'mcp_coingecko'."""

    display_name: str
    """Human-readable name for UI display."""

    description: str
    """Description shown in the tool catalog."""

    url: str
    """MCP server HTTP endpoint URL."""

    transport: Literal["sse", "streamable_http"]
    """Transport type."""

    api_key_config_attr: str | None = None
    """Attribute name on config object, e.g. 'coingecko_api_key'."""

    api_key_header: str | None = None
    """HTTP header name to send the API key, e.g. 'Authorization'."""

    api_key_prefix: str | None = "Bearer"
    """Prefix for the API key value, e.g. 'Bearer'. Set to None for raw key."""

    tags: list[str] = field(default_factory=list)
    """Tags for catalog categorization."""

    web3: bool = False
    """Whether the server belongs to the web3/crypto domain (grouping only)."""

    wallet: bool = False
    """Whether the server's tools operate on team wallets."""

    icon: str | None = None
    """Icon URL path served by the API, e.g. '/tools/mcp_coingecko/coingecko.svg'."""


MCP_SERVERS: dict[str, McpServerDef] = {
    "mcp_coingecko": McpServerDef(
        name="mcp_coingecko",
        display_name="CoinGecko",
        description="Crypto market data, prices, trends, and analytics via CoinGecko API",
        url="https://mcp.api.coingecko.com/sse",
        transport="sse",
        api_key_config_attr="coingecko_api_key",
        api_key_header="x-cg-demo-api-key",
        api_key_prefix=None,
        tags=["Crypto", "Market Data"],
        web3=True,
        icon="/tools/mcp_coingecko/coingecko.svg",
    ),
}
