"""Capital flow (资金流向) for an individual stock or the whole market."""

from typing import Any, Literal

import akshare as ak
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.tools.cn_stock.base import (
    CNStockBaseTool,
    market_of,
    normalize_a_share_symbol,
)


class GetCapitalFlowInput(BaseModel):
    scope: Literal["stock", "market"] = Field(
        ...,
        description="'stock' for individual flow (requires symbol); 'market' for whole-market flow.",
    )
    symbol: str | None = Field(
        default=None,
        description="6-digit A-share code; required when scope='stock'.",
    )
    days: int = Field(
        default=5,
        description="Number of recent trading days to return (1-30).",
        ge=1,
        le=30,
    )


class GetCapitalFlow(CNStockBaseTool):
    name: str = "cn_stock_get_capital_flow"
    title: str = "Get Capital Flow"
    description: str = (
        "Get net capital inflow / outflow data. For an individual stock returns recent "
        "main / retail / institutional flows; for the whole market returns aggregate "
        "north-bound and main-fund flows. Use to gauge smart-money positioning."
    )
    args_schema: ArgsSchema | None = GetCapitalFlowInput

    async def _arun(
        self,
        scope: Literal["stock", "market"],
        symbol: str | None = None,
        days: int = 5,
        **_: Any,
    ) -> list[dict[str, Any]]:
        if scope == "stock":
            if not symbol:
                raise ToolException("symbol is required when scope='stock'")
            code = normalize_a_share_symbol(symbol)
            mkt = market_of(symbol)
            rows: list[dict[str, Any]] = await self.run_blocking(
                f"flow:stock:{code}",
                300,
                ak.stock_individual_fund_flow,
                stock=code,
                market=mkt,
            )
            return rows[-days:] if rows else []

        rows = await self.run_blocking(
            "flow:market",
            300,
            ak.stock_market_fund_flow,
        )
        return rows[-days:] if rows else []
