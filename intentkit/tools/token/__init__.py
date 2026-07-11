"""Token tools for blockchain token analysis."""

from intentkit.config.config import config as system_config
from intentkit.tools.meta import ToolsetMeta
from intentkit.tools.token.base import TokenBaseTool
from intentkit.tools.token.erc20_transfers import ERC20Transfers
from intentkit.tools.token.token_analytics import TokenAnalytics
from intentkit.tools.token.token_price import TokenPrice
from intentkit.tools.token.token_search import TokenSearch

toolset = ToolsetMeta(
    title="Token Tools",
    description="Token analysis tools powered by Moralis API",
    tags=["Analytics", "Crypto"],
    web3=True,
    icon="/tools/portfolio/moralis.png",
)


# Cache tools at the system level, because they are stateless
_cache: dict[str, TokenBaseTool] = {}

_TOOL_NAME_TO_CLASS_MAP: dict[str, type[TokenBaseTool]] = {
    "token_price": TokenPrice,
    "token_erc20_transfers": ERC20Transfers,
    "token_search": TokenSearch,
    "token_analytics": TokenAnalytics,
}


async def get_tools(tool_names: list[str], **_) -> list[TokenBaseTool]:
    """Return Token tool instances for the requested names.

    Unknown names are skipped silently.
    """
    tools: list[TokenBaseTool] = []
    for name in tool_names:
        tool = get_token_tool(name)
        if tool:
            tools.append(tool)
    return tools


def get_token_tool(tool_name: str) -> TokenBaseTool | None:
    """Get a Token blockchain analysis tool by name, with caching."""
    if tool_name in _cache:
        return _cache[tool_name]

    tool_class = _TOOL_NAME_TO_CLASS_MAP.get(tool_name)
    if not tool_class:
        return None

    _cache[tool_name] = tool_class()  # pyright: ignore[reportCallIssue]
    return _cache[tool_name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.moralis_api_key)
