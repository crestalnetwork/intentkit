from collections.abc import Callable

from intentkit.tools.meta import ToolsetMeta
from intentkit.tools.pancakeswap.add_liquidity import PancakeSwapAddLiquidity
from intentkit.tools.pancakeswap.base import PancakeSwapBaseTool
from intentkit.tools.pancakeswap.get_positions import PancakeSwapGetPositions
from intentkit.tools.pancakeswap.quote import PancakeSwapQuote
from intentkit.tools.pancakeswap.remove_liquidity import PancakeSwapRemoveLiquidity
from intentkit.tools.pancakeswap.swap import PancakeSwapSwap

toolset = ToolsetMeta(
    title="PancakeSwap",
    description="Swap tokens and manage V3 liquidity positions on PancakeSwap DEX",
    tags=["DeFi"],
    wallet=True,
    icon="/tools/pancakeswap/pancakeswap.png",
)


_cache: dict[str, PancakeSwapBaseTool] = {}

_TOOL_CLASSES: dict[str, Callable[[], PancakeSwapBaseTool]] = {
    "pancakeswap_quote": PancakeSwapQuote,
    "pancakeswap_swap": PancakeSwapSwap,
    "pancakeswap_get_positions": PancakeSwapGetPositions,
    "pancakeswap_add_liquidity": PancakeSwapAddLiquidity,
    "pancakeswap_remove_liquidity": PancakeSwapRemoveLiquidity,
}


async def get_tools(tool_names: list[str], **_) -> list[PancakeSwapBaseTool]:
    """Get the requested PancakeSwap tools; unknown names are skipped."""
    return [tool for name in tool_names if (tool := get_pancakeswap_tool(name))]


def get_pancakeswap_tool(tool_name: str) -> PancakeSwapBaseTool | None:
    """Get a PancakeSwap tool by name, using the instance cache."""
    if tool_name in _cache:
        return _cache[tool_name]
    cls = _TOOL_CLASSES.get(tool_name)
    if cls is None:
        return None
    _cache[tool_name] = cls()
    return _cache[tool_name]


def available() -> bool:
    """PancakeSwap requires no platform API keys."""
    return True
