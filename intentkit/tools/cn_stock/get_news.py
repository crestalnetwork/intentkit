"""Stock-specific or macro financial news via akshare."""

from typing import Any, Literal

import akshare as ak
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.tools.cn_stock.base import CNStockBaseTool, normalize_a_share_symbol


class GetNewsInput(BaseModel):
    scope: Literal["stock", "macro"] = Field(
        ...,
        description="'stock' for news of a single ticker (requires symbol); 'macro' for top financial headlines.",
    )
    symbol: str | None = Field(
        default=None,
        description="6-digit A-share code; required when scope='stock'.",
    )
    limit: int = Field(
        default=10,
        description="Maximum number of news items to return (1-50).",
        ge=1,
        le=50,
    )


class GetNews(CNStockBaseTool):
    name: str = "cn_stock_get_news"
    title: str = "Get News"
    description: str = (
        "Get recent news for a specific A-share or top macro financial headlines. "
        "Use for sentiment context before deeper analysis."
    )
    args_schema: ArgsSchema | None = GetNewsInput

    async def _arun(
        self,
        scope: Literal["stock", "macro"],
        symbol: str | None = None,
        limit: int = 10,
        **_: Any,
    ) -> list[dict[str, Any]]:
        if scope == "stock":
            if not symbol:
                raise ToolException("symbol is required when scope='stock'")
            code = normalize_a_share_symbol(symbol)
            rows: list[dict[str, Any]] = await self.run_blocking(
                f"news:stock:{code}",
                300,
                ak.stock_news_em,
                symbol=code,
            )
            return rows[:limit] if rows else []

        rows = await self.run_blocking(
            "news:macro",
            300,
            ak.stock_info_global_em,
        )
        return rows[:limit] if rows else []
