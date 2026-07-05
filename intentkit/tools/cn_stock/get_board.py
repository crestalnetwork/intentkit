"""Industry/concept board snapshot via akshare."""

from typing import Any, Literal

import akshare as ak
from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.tools.cn_stock.base import CNStockBaseTool


class GetBoardInput(BaseModel):
    kind: Literal["industry", "concept"] = Field(
        default="industry",
        description="'industry' (行业板块) or 'concept' (概念板块).",
    )
    top: int = Field(
        default=20,
        description="Return top-N gainers and bottom-N losers by % change (1-50).",
        ge=1,
        le=50,
    )


class GetBoard(CNStockBaseTool):
    name: str = "cn_stock_get_board"
    title: str = "Get Board"
    description: str = (
        "Get a snapshot of industry or concept boards, sorted by intraday percentage "
        "change. Use to identify hot sectors and rotation. Returns top gainers and "
        "top losers."
    )
    args_schema: ArgsSchema | None = GetBoardInput

    async def _arun(
        self,
        kind: Literal["industry", "concept"] = "industry",
        top: int = 20,
        **_: Any,
    ) -> dict[str, Any]:
        fetcher = (
            ak.stock_board_industry_name_em
            if kind == "industry"
            else ak.stock_board_concept_name_em
        )
        rows: list[dict[str, Any]] = await self.run_blocking(
            f"board:{kind}",
            60,
            fetcher,
        )

        def pct(r: dict[str, Any]) -> float:
            v = r.get("涨跌幅")
            try:
                return float(v) if v is not None else 0.0
            except (TypeError, ValueError):
                return 0.0

        ranked = sorted(rows, key=pct, reverse=True)
        return {
            "kind": kind,
            "gainers": ranked[:top],
            "losers": ranked[-top:][::-1],
        }
