"""Fundamental / financial metrics for an A-share via akshare."""

from typing import Any, Literal

import akshare as ak
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.tools.cn_stock.base import CNStockBaseTool, normalize_a_share_symbol


class GetFinancialsInput(BaseModel):
    symbol: str = Field(..., description="6-digit A-share code, e.g. '600519'.")
    indicator: Literal["按报告期", "按年度", "按单季度"] = Field(
        default="按报告期",
        description="Reporting cadence to fetch.",
    )
    limit: int = Field(
        default=8,
        description="Maximum number of recent reporting periods to return (1-40).",
        ge=1,
        le=40,
    )


class GetFinancials(CNStockBaseTool):
    name: str = "cn_stock_get_financials"
    title: str = "Get Financials"
    description: str = (
        "Get key financial metrics (EPS, ROE, profit, revenue, margins, growth) for "
        "an A-share by reporting period. Use for fundamental analysis and trend tracking."
    )
    args_schema: ArgsSchema | None = GetFinancialsInput

    async def _arun(
        self,
        symbol: str,
        indicator: Literal["按报告期", "按年度", "按单季度"] = "按报告期",
        limit: int = 8,
        **_: Any,
    ) -> list[dict[str, Any]]:
        code = normalize_a_share_symbol(symbol)
        rows: list[dict[str, Any]] = await self.run_blocking(
            f"financials:{code}:{indicator}",
            21600,
            ak.stock_financial_abstract_ths,
            symbol=code,
            indicator=indicator,
        )
        if not rows:
            raise ToolException(f"No financials returned for {code}")
        return rows[:limit]
