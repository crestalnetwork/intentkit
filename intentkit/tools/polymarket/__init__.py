"""Polymarket prediction market tools."""

from intentkit.tools.meta import ToolsetMeta
from intentkit.tools.polymarket.base import PolymarketBaseTool
from intentkit.tools.polymarket.cancel_order import CancelOrder
from intentkit.tools.polymarket.get_market import GetMarket
from intentkit.tools.polymarket.get_orderbook import GetOrderbook
from intentkit.tools.polymarket.get_orders import GetOrders
from intentkit.tools.polymarket.get_positions import GetPositions
from intentkit.tools.polymarket.get_price_history import GetPriceHistory
from intentkit.tools.polymarket.get_trades import GetTrades
from intentkit.tools.polymarket.place_order import PlaceOrder
from intentkit.tools.polymarket.search_markets import SearchMarkets

toolset = ToolsetMeta(
    title="Polymarket",
    description="Integration with Polymarket prediction market for browsing markets, checking prices, and trading outcome tokens",
    tags=["Crypto", "Analytics"],
    web3=True,
    icon="/tools/polymarket/polymarket.png",
)


# Cache tools at the system level, because they are stateless
_cache: dict[str, PolymarketBaseTool] = {}

_TOOL_NAME_TO_CLASS_MAP: dict[str, type[PolymarketBaseTool]] = {
    "polymarket_search_markets": SearchMarkets,
    "polymarket_get_market": GetMarket,
    "polymarket_get_orderbook": GetOrderbook,
    "polymarket_get_price_history": GetPriceHistory,
    "polymarket_place_order": PlaceOrder,
    "polymarket_cancel_order": CancelOrder,
    "polymarket_get_positions": GetPositions,
    "polymarket_get_orders": GetOrders,
    "polymarket_get_trades": GetTrades,
}


async def get_tools(tool_names: list[str], **_) -> list[PolymarketBaseTool]:
    """Return Polymarket tool instances for the requested names.

    Unknown names are skipped silently.
    """
    tools: list[PolymarketBaseTool] = []
    for name in tool_names:
        tool = get_polymarket_tool(name)
        if tool:
            tools.append(tool)
    return tools


def get_polymarket_tool(tool_name: str) -> PolymarketBaseTool | None:
    """Get a Polymarket tool by name, with caching."""
    if tool_name in _cache:
        return _cache[tool_name]

    tool_class = _TOOL_NAME_TO_CLASS_MAP.get(tool_name)
    if not tool_class:
        return None

    _cache[tool_name] = tool_class()  # pyright: ignore[reportCallIssue]
    return _cache[tool_name]


def available() -> bool:
    """Check if Polymarket tools are available.

    Always returns True since public tools need no API keys.
    Authenticated tools check wallet at runtime.
    """
    return True
