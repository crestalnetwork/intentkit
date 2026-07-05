"""Daily/weekly/monthly K-line history for an A-share via akshare."""

from datetime import timedelta
from typing import Any, Literal

import akshare as ak
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.tools.cn_stock.base import (
    CNStockBaseTool,
    normalize_a_share_symbol,
    today_cn,
)

Period = Literal["daily", "weekly", "monthly"]
Adjust = Literal["", "qfq", "hfq"]


class GetKLineInput(BaseModel):
    symbol: str = Field(..., description="6-digit A-share code, e.g. '600519'.")
    period: Period = Field(
        default="daily", description="K-line period: daily / weekly / monthly."
    )
    days_back: int = Field(
        default=90,
        description="Number of calendar days of history to load (1-1825).",
        ge=1,
        le=1825,
    )
    adjust: Adjust = Field(
        default="qfq",
        description="Price adjustment: '' raw, 'qfq' forward-adjusted, 'hfq' back-adjusted.",
    )


class GetKLine(CNStockBaseTool):
    name: str = "cn_stock_get_kline"
    title: str = "Get K-Line"
    description: str = (
        "Get historical K-line bars (open/high/low/close/volume) for a single A-share. "
        "Forward-adjusted (qfq) by default. Use for trend, volatility and pattern analysis."
    )
    args_schema: ArgsSchema | None = GetKLineInput

    async def _arun(
        self,
        symbol: str,
        period: Period = "daily",
        days_back: int = 90,
        adjust: Adjust = "qfq",
        **_: Any,
    ) -> list[dict[str, Any]]:
        code = normalize_a_share_symbol(symbol)
        end = today_cn()
        start = end - timedelta(days=days_back)
        cache_key = f"kline:{code}:{period}:{adjust}:{start:%Y%m%d}:{end:%Y%m%d}"
        rows = await self.run_blocking(
            cache_key,
            900,
            ak.stock_zh_a_hist,
            symbol=code,
            period=period,
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust=adjust,
        )
        if not rows:
            raise ToolException(
                f"No K-line data for {code} between {start} and {end}; symbol may be delisted."
            )
        return rows
