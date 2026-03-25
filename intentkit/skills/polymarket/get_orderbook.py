"""Polymarket skill: get order book for a market token."""

import json
from decimal import Decimal
from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.polymarket.base import PolymarketBaseTool


class GetOrderbookInput(BaseModel):
    """Input for getting order book."""

    token_id: str = Field(
        description=(
            "The token ID of the outcome to get order book for. "
            "Get token IDs from the get_market skill."
        ),
    )


class GetOrderbook(PolymarketBaseTool):
    """Get the order book for a specific Polymarket outcome token.

    Returns current bids and asks with prices and sizes,
    plus summary stats like best bid/ask and spread.
    """

    name: str = "polymarket_get_orderbook"
    description: str = (
        "Get the order book (bids and asks) for a Polymarket outcome token. "
        "Shows current buy and sell orders with prices and sizes. "
        "Also returns best bid, best ask, spread, and last trade price."
    )
    args_schema: ArgsSchema | None = GetOrderbookInput
    price: Decimal = Decimal("1")

    async def _arun(self, token_id: str, **kwargs: Any) -> str:
        await self.global_rate_limit_by_skill(limit=500, seconds=60)

        data = await self._clob_get("/book", params={"token_id": token_id})

        bids = data.get("bids", [])
        asks = data.get("asks", [])

        # Calculate summary
        best_bid = float(bids[0]["price"]) if bids else 0
        best_ask = float(asks[0]["price"]) if asks else 0
        spread = best_ask - best_bid if best_bid and best_ask else 0

        result = {
            "token_id": token_id,
            "bids": bids[:10],  # Top 10 levels
            "asks": asks[:10],
            "summary": {
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread": round(spread, 4),
                "bid_depth": len(bids),
                "ask_depth": len(asks),
            },
        }

        # Add market metadata if available
        market_info = data.get("market", {})
        if market_info:
            result["tick_size"] = market_info.get("min_tick_size", "0.01")
            result["last_trade_price"] = data.get("last_trade_price", "N/A")

        return json.dumps(result)
