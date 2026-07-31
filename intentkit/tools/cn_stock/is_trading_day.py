"""Check whether a given date is an A-share trading day."""

from datetime import date, datetime
from typing import Any

import akshare as ak
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.tools.cn_stock.base import CNStockBaseTool, today_cn


class IsTradingDayInput(BaseModel):
    on_date: str | None = Field(
        default=None,
        description="Date in YYYY-MM-DD or YYYYMMDD; defaults to today (Asia/Shanghai).",
    )


class IsTradingDay(CNStockBaseTool):
    name: str = "cn_stock_is_trading_day"
    title: str = "Is Trading Day"
    description: str = (
        "Check whether a given date is an A-share trading day (excludes weekends and "
        "Chinese stock-market holidays). Always call this at the start of a scheduled "
        "task before doing further analysis — cron triggers do not skip holidays."
    )
    args_schema: ArgsSchema | None = IsTradingDayInput

    async def _arun(
        self,
        on_date: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        target = self._parse(on_date) if on_date else today_cn()
        rows: list[dict[str, Any]] = await self.run_blocking(
            "trade_calendar",
            86400,
            ak.tool_trade_date_hist_sina,
        )
        trading = {self._row_date(r) for r in rows}
        is_open = target.isoformat() in trading
        return {"date": target.isoformat(), "is_trading_day": is_open}

    @staticmethod
    def _parse(s: str) -> date:
        s = s.strip()
        for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
            try:
                # Date-only parse; a timezone would be meaningless here.
                return datetime.strptime(s, fmt).date()  # noqa: DTZ007
            except ValueError:
                continue
        raise ToolException(f"Cannot parse date: {s!r}")

    @staticmethod
    def _row_date(row: dict[str, Any]) -> str:
        v = row.get("trade_date")
        if isinstance(v, str):
            return v[:10]
        return str(v)[:10]
