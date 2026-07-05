"""Chinese A-share market data tools (akshare-backed)."""

from typing import Any

from intentkit.tools.cn_stock.base import CNStockBaseTool
from intentkit.tools.cn_stock.get_announcement import GetAnnouncement
from intentkit.tools.cn_stock.get_board import GetBoard
from intentkit.tools.cn_stock.get_capital_flow import GetCapitalFlow
from intentkit.tools.cn_stock.get_financials import GetFinancials
from intentkit.tools.cn_stock.get_index import GetIndex
from intentkit.tools.cn_stock.get_kline import GetKLine
from intentkit.tools.cn_stock.get_news import GetNews
from intentkit.tools.cn_stock.get_quote import GetQuote
from intentkit.tools.cn_stock.is_trading_day import IsTradingDay
from intentkit.tools.meta import ToolsetMeta

toolset = ToolsetMeta(
    title="China A-Share",
    description="Real-time and historical market data for Chinese A-shares (Shanghai/Shenzhen/Beijing) backed by the akshare library — quotes, K-lines, indices, boards, capital flow, news, announcements, financials, and trading-day calendar.",
    tags=["Analytics", "Stocks", "China"],
)


# Tool instances are stateless across calls; build once at import and reuse.
_TOOLS: dict[str, CNStockBaseTool] = {
    "cn_stock_get_quote": GetQuote(),
    "cn_stock_get_kline": GetKLine(),
    "cn_stock_get_index": GetIndex(),
    "cn_stock_get_board": GetBoard(),
    "cn_stock_get_capital_flow": GetCapitalFlow(),
    "cn_stock_get_news": GetNews(),
    "cn_stock_get_announcement": GetAnnouncement(),
    "cn_stock_get_financials": GetFinancials(),
    "cn_stock_is_trading_day": IsTradingDay(),
}


async def get_tools(tool_names: list[str], **_: Any) -> list[CNStockBaseTool]:
    """Return cn_stock tool instances for the requested names."""
    return [_TOOLS[name] for name in tool_names if name in _TOOLS]
