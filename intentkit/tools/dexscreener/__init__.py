import logging

from intentkit.tools.dexscreener.base import DexScreenerBaseTool
from intentkit.tools.dexscreener.get_pair_info import GetPairInfo
from intentkit.tools.dexscreener.get_token_pairs import GetTokenPairs
from intentkit.tools.dexscreener.get_tokens_info import GetTokensInfo
from intentkit.tools.dexscreener.search_token import SearchToken
from intentkit.tools.meta import ToolsetMeta

toolset = ToolsetMeta(
    title="Dexscreener",
    description="Integration with DexScreener API, enabling crypto token pair information",
    tags=["Analytics", "DeFi"],
    icon="/tools/dexscreener/dexscreener.png",
)


# Cache tools at the system level, because they are stateless
_cache: dict[str, DexScreenerBaseTool] = {}

logger = logging.getLogger(__name__)

_TOOL_NAME_TO_CLASS_MAP: dict[str, type[DexScreenerBaseTool]] = {
    "dexscreener_search_token": SearchToken,
    "dexscreener_get_pair_info": GetPairInfo,
    "dexscreener_get_token_pairs": GetTokenPairs,
    "dexscreener_get_tokens_info": GetTokensInfo,
}


async def get_tools(tool_names: list[str], **_) -> list[DexScreenerBaseTool]:
    """Get the requested DexScreener tools."""
    return [tool for name in tool_names if (tool := get_dexscreener_tool(name))]


def get_dexscreener_tool(tool_name: str) -> DexScreenerBaseTool | None:
    """Get a DexScreener tool by name."""
    # Return from cache immediately if already exists
    if tool_name in _cache:
        return _cache[tool_name]

    tool_class = _TOOL_NAME_TO_CLASS_MAP.get(tool_name)
    if not tool_class:
        logger.warning("Unknown Dexscreener tool: %s", tool_name)
        return None

    _cache[tool_name] = tool_class()  # pyright: ignore[reportCallIssue]
    return _cache[tool_name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return True
