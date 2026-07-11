"""Aerodrome DEX tools (Base network)."""

from typing import Any

from intentkit.tools.aerodrome.add_liquidity import AerodromeAddLiquidity
from intentkit.tools.aerodrome.base import AerodromeBaseTool
from intentkit.tools.aerodrome.get_positions import AerodromeGetPositions
from intentkit.tools.aerodrome.quote import AerodromeQuote
from intentkit.tools.aerodrome.remove_liquidity import AerodromeRemoveLiquidity
from intentkit.tools.aerodrome.swap import AerodromeSwap
from intentkit.tools.meta import ToolsetMeta

toolset = ToolsetMeta(
    title="Aerodrome",
    description="Swap tokens and manage Slipstream CL liquidity positions on Aerodrome DEX (Base)",
    tags=["DeFi"],
    wallet=True,
    icon="/tools/aerodrome/aerodrome.svg",
)


_cache: dict[str, AerodromeBaseTool] = {}

_TOOL_CLASSES: dict[str, type[AerodromeBaseTool]] = {
    "aerodrome_quote": AerodromeQuote,
    "aerodrome_swap": AerodromeSwap,
    "aerodrome_get_positions": AerodromeGetPositions,
    "aerodrome_add_liquidity": AerodromeAddLiquidity,
    "aerodrome_remove_liquidity": AerodromeRemoveLiquidity,
}


async def get_tools(tool_names: list[str], **_: Any) -> list[AerodromeBaseTool]:
    """Return Aerodrome tool instances for the requested names."""
    result: list[AerodromeBaseTool] = []
    for name in tool_names:
        tool = _get_tool(name)
        if tool:
            result.append(tool)
    return result


def _get_tool(name: str) -> AerodromeBaseTool | None:
    tool_class = _TOOL_CLASSES.get(name)
    if tool_class is None:
        return None
    if name not in _cache:
        _cache[name] = tool_class()  # pyright: ignore[reportCallIssue]
    return _cache[name]


def available() -> bool:
    """Aerodrome requires no platform API keys."""
    return True
