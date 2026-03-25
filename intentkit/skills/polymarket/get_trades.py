"""Polymarket skill: get trade history."""

import json
from decimal import Decimal
from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.polymarket.base import PolymarketBaseTool


class GetTradesInput(BaseModel):
    """Input for getting trade history."""

    market: str | None = Field(
        default=None,
        description="Filter by market condition_id. Leave empty for all.",
    )
    limit: int = Field(
        default=20,
        description="Maximum number of trades to return (1-100)",
        ge=1,
        le=100,
    )


class GetTrades(PolymarketBaseTool):
    """Get trade history for the agent's wallet on Polymarket.

    Shows completed trades with execution prices, sizes, and timestamps.
    """

    name: str = "polymarket_get_trades"
    description: str = (
        "Get trade history on Polymarket for the agent's wallet. "
        "Shows executed trades with prices, sizes, and timestamps. "
        "Optionally filter by market."
    )
    args_schema: ArgsSchema | None = GetTradesInput
    price: Decimal = Decimal("5")

    async def _arun(
        self,
        market: str | None = None,
        limit: int = 20,
        **kwargs: Any,
    ) -> str:
        self._require_wallet("view trades")

        await self.user_rate_limit_by_skill(limit=30, seconds=60)

        params: dict[str, Any] = {}
        if market:
            params["market"] = market

        data = await self._clob_auth_get("/trades", params=params)

        raw_trades: list[Any] = (
            data if isinstance(data, list) else data.get("trades", [])
        )

        formatted = []
        for trade in raw_trades[:limit]:
            if not isinstance(trade, dict):
                continue
            formatted.append(
                {
                    "trade_id": trade.get("id", ""),
                    "market": trade.get("market", ""),
                    "token_id": trade.get("asset_id", trade.get("tokenId", "")),
                    "side": trade.get("side", ""),
                    "price": trade.get("price", ""),
                    "size": trade.get("size", ""),
                    "fee": trade.get("fee", ""),
                    "timestamp": trade.get("created_at", trade.get("timestamp", "")),
                    "status": trade.get("status", "MATCHED"),
                    "order_id": trade.get("order_id", trade.get("orderId", "")),
                }
            )

        return json.dumps(
            {
                "trades": formatted,
                "count": len(formatted),
            }
        )
