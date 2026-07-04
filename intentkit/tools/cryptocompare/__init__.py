"""CryptoCompare tools."""

import logging
from collections.abc import Callable

from intentkit.config.config import config as system_config
from intentkit.tools.cryptocompare.base import CryptoCompareBaseTool
from intentkit.tools.cryptocompare.fetch_news import CryptoCompareFetchNews
from intentkit.tools.cryptocompare.fetch_price import CryptoCompareFetchPrice
from intentkit.tools.cryptocompare.fetch_top_exchanges import (
    CryptoCompareFetchTopExchanges,
)
from intentkit.tools.cryptocompare.fetch_top_market_cap import (
    CryptoCompareFetchTopMarketCap,
)
from intentkit.tools.cryptocompare.fetch_top_volume import CryptoCompareFetchTopVolume
from intentkit.tools.cryptocompare.fetch_trading_signals import (
    CryptoCompareFetchTradingSignals,
)

# Cache tools at the system level, because they are stateless
_cache: dict[str, CryptoCompareBaseTool] = {}

logger = logging.getLogger(__name__)

_TOOL_CLASSES: dict[str, Callable[[], CryptoCompareBaseTool]] = {
    "cryptocompare_fetch_news": CryptoCompareFetchNews,
    "cryptocompare_fetch_price": CryptoCompareFetchPrice,
    "cryptocompare_fetch_trading_signals": CryptoCompareFetchTradingSignals,
    "cryptocompare_fetch_top_market_cap": CryptoCompareFetchTopMarketCap,
    "cryptocompare_fetch_top_exchanges": CryptoCompareFetchTopExchanges,
    "cryptocompare_fetch_top_volume": CryptoCompareFetchTopVolume,
}


async def get_tools(tool_names: list[str], **_) -> list[CryptoCompareBaseTool]:
    """Get the requested CryptoCompare tools."""
    return [tool for name in tool_names if (tool := get_cryptocompare_tool(name))]


def get_cryptocompare_tool(tool_name: str) -> CryptoCompareBaseTool | None:
    """Get a CryptoCompare tool by name."""
    if tool_name not in _cache:
        tool_class = _TOOL_CLASSES.get(tool_name)
        if tool_class is None:
            logger.warning("Unknown CryptoCompare tool: %s", tool_name)
            return None
        _cache[tool_name] = tool_class()
    return _cache[tool_name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.cryptocompare_api_key)
