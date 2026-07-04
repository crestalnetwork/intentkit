"""Pyth price oracle tools."""

from intentkit.tools.pyth.base import PythBaseTool
from intentkit.tools.pyth.fetch_price import PythFetchPrice
from intentkit.tools.pyth.fetch_price_feed import PythFetchPriceFeed

# Cache for stateless tools
_cache: dict[str, PythBaseTool] = {
    "pyth_fetch_price": PythFetchPrice(),
    "pyth_fetch_price_feed": PythFetchPriceFeed(),
}


async def get_tools(tool_names: list[str], **_) -> list[PythBaseTool]:
    """Return Pyth tool instances for the requested names.

    Unknown names are skipped silently.
    """
    return [_cache[name] for name in tool_names if name in _cache]


def get_pyth_tool(tool_name: str) -> PythBaseTool | None:
    """Get a Pyth tool by name."""
    return _cache.get(tool_name)


def available() -> bool:
    """Check if this toolset is available based on system config.

    Pyth tools only require HTTP access to the Pyth Hermes API,
    so they are always available.
    """
    return True
