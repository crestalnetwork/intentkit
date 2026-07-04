"""Uniswap DEX tools."""

from intentkit.tools.uniswap.add_liquidity import UniswapAddLiquidity
from intentkit.tools.uniswap.base import UniswapBaseTool
from intentkit.tools.uniswap.get_positions import UniswapGetPositions
from intentkit.tools.uniswap.quote import UniswapQuote
from intentkit.tools.uniswap.remove_liquidity import UniswapRemoveLiquidity
from intentkit.tools.uniswap.swap import UniswapSwap

# Cache tools at the system level, because they are stateless
_cache: dict[str, UniswapBaseTool] = {}

_TOOL_NAME_TO_CLASS_MAP: dict[str, type[UniswapBaseTool]] = {
    "uniswap_quote": UniswapQuote,
    "uniswap_swap": UniswapSwap,
    "uniswap_get_positions": UniswapGetPositions,
    "uniswap_add_liquidity": UniswapAddLiquidity,
    "uniswap_remove_liquidity": UniswapRemoveLiquidity,
}


async def get_tools(tool_names: list[str], **_) -> list[UniswapBaseTool]:
    """Return Uniswap tool instances for the requested names.

    Unknown names are skipped silently.
    """
    tools: list[UniswapBaseTool] = []
    for name in tool_names:
        tool = get_uniswap_tool(name)
        if tool:
            tools.append(tool)
    return tools


def get_uniswap_tool(tool_name: str) -> UniswapBaseTool | None:
    """Get a Uniswap tool by name, with caching."""
    if tool_name in _cache:
        return _cache[tool_name]

    tool_class = _TOOL_NAME_TO_CLASS_MAP.get(tool_name)
    if not tool_class:
        return None

    _cache[tool_name] = tool_class()  # pyright: ignore[reportCallIssue]
    return _cache[tool_name]


def available() -> bool:
    """Uniswap requires no platform API keys."""
    return True
