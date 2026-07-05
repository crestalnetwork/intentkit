"""Real-time spot quote for one or more A-share stocks via akshare."""

from typing import Any

import akshare as ak
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.tools.cn_stock.base import CNStockBaseTool, normalize_a_share_symbol

QUOTE_COLUMNS = [
    "代码",
    "名称",
    "最新价",
    "涨跌幅",
    "涨跌额",
    "成交量",
    "成交额",
    "振幅",
    "最高",
    "最低",
    "今开",
    "昨收",
    "换手率",
    "市盈率-动态",
    "市净率",
    "总市值",
    "流通市值",
]


class GetQuoteInput(BaseModel):
    symbols: list[str] = Field(
        ...,
        description="List of A-share codes (e.g. ['600519', '000001']). Max 50 per call.",
        max_length=50,
        min_length=1,
    )


class GetQuote(CNStockBaseTool):
    name: str = "cn_stock_get_quote"
    title: str = "Get Quote"
    description: str = (
        "Get real-time spot quote for one or more A-share stocks. "
        "Returns price, change %, volume, turnover, P/E, P/B, and market cap. "
        "Use 6-digit codes such as '600519' or '000001'."
    )
    args_schema: ArgsSchema | None = GetQuoteInput

    async def _arun(self, symbols: list[str], **_: Any) -> list[dict[str, Any]]:
        codes = [normalize_a_share_symbol(s) for s in symbols]
        all_rows: list[dict[str, Any]] = await self.run_blocking(
            "spot_a_em",
            10,
            self._fetch_spot,
        )
        wanted = set(codes)
        result = [r for r in all_rows if str(r.get("代码", "")) in wanted]
        if not result:
            raise ToolException(
                f"No quotes returned for {symbols}; codes may be invalid or market is closed."
            )
        return result

    @staticmethod
    def _fetch_spot() -> Any:
        df = ak.stock_zh_a_spot_em()
        keep = [c for c in QUOTE_COLUMNS if c in df.columns]
        if not keep:
            raise ToolException(
                "akshare quote schema changed: no expected columns found"
            )
        return df[keep]
