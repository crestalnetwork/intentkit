"""WETH wrapping/unwrapping tools."""

from intentkit.tools.weth.base import WethBaseTool
from intentkit.tools.weth.unwrap_eth import WETHUnwrapEth
from intentkit.tools.weth.wrap_eth import WETHWrapEth

# Cache for tool instances
_cache: dict[str, WethBaseTool] = {
    "weth_wrap_eth": WETHWrapEth(),
    "weth_unwrap_eth": WETHUnwrapEth(),
}


async def get_tools(tool_names: list[str], **_) -> list[WethBaseTool]:
    """Return WETH tool instances for the requested names.

    Unknown names are skipped silently.
    """
    return [_cache[name] for name in tool_names if name in _cache]


def get_weth_tool(tool_name: str) -> WethBaseTool | None:
    """Get a WETH tool by name."""
    return _cache.get(tool_name)


def available() -> bool:
    """Check if this toolset is available based on system config.

    WETH tools are available for any EVM-compatible wallet (CDP, Safe/Privy)
    on networks that have WETH deployed.
    """
    return True
