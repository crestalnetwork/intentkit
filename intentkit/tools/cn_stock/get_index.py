"""Major Chinese market index spot and history via akshare."""

import asyncio
from datetime import timedelta
from typing import Any, Literal

import akshare as ak
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.tools.cn_stock.base import CNStockBaseTool, today_cn

# Friendly names to akshare codes used by index_zh_a_hist.
INDEX_CODES: dict[str, str] = {
    "上证指数": "000001",
    "沪深300": "000300",
    "中证500": "000905",
    "中证1000": "000852",
    "深证成指": "399001",
    "创业板指": "399006",
    "科创50": "000688",
}

DEFAULT_INDICES = ["上证指数", "深证成指", "创业板指", "沪深300"]


class GetIndexInput(BaseModel):
    indices: list[str] = Field(
        default_factory=lambda: list(DEFAULT_INDICES),
        description=(
            "Index names. Allowed: " + ", ".join(INDEX_CODES) + ". "
            "Defaults to the four headline indices."
        ),
    )
    history: Literal["spot", "30d"] = Field(
        default="spot",
        description="'spot' returns latest snapshot only; '30d' adds 30 daily bars.",
    )


class GetIndex(CNStockBaseTool):
    name: str = "cn_stock_get_index"
    title: str = "Get Index"
    description: str = (
        "Get spot value (and optional 30-day history) for major Chinese stock indices "
        "such as 上证指数, 深证成指, 创业板指, 沪深300. Use to gauge overall market direction."
    )
    args_schema: ArgsSchema | None = GetIndexInput

    async def _arun(
        self,
        indices: list[str] | None = None,
        history: Literal["spot", "30d"] = "spot",
        **_: Any,
    ) -> dict[str, Any]:
        names = indices if indices is not None else list(DEFAULT_INDICES)
        unknown = [n for n in names if n not in INDEX_CODES]
        if unknown:
            raise ToolException(
                f"Unknown index names: {unknown}. Allowed: {list(INDEX_CODES)}"
            )

        spot_rows: list[dict[str, Any]] = await self.run_blocking(
            "index_spot_em",
            30,
            ak.stock_zh_index_spot_em,
            symbol="沪深重要指数",
        )
        spot_by_name = {r.get("名称"): r for r in spot_rows}
        result: dict[str, Any] = {
            "spot": [spot_by_name[n] for n in names if n in spot_by_name],
        }

        if history == "30d":
            end = today_cn()
            start = end - timedelta(days=45)
            hist_results = await asyncio.gather(
                *(
                    self.run_blocking(
                        f"index_hist:{INDEX_CODES[name]}:{start:%Y%m%d}:{end:%Y%m%d}",
                        1800,
                        ak.index_zh_a_hist,
                        symbol=INDEX_CODES[name],
                        period="daily",
                        start_date=start.strftime("%Y%m%d"),
                        end_date=end.strftime("%Y%m%d"),
                    )
                    for name in names
                )
            )
            result["history"] = {
                name: (hist[-30:] if isinstance(hist, list) else [])
                for name, hist in zip(names, hist_results)
            }

        return result
