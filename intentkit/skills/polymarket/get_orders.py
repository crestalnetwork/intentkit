"""Polymarket skill: get open orders."""

import json
from decimal import Decimal
from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.polymarket.base import PolymarketBaseTool


class GetOrdersInput(BaseModel):
    """Input for getting orders."""

    market: str | None = Field(
        default=None,
        description="Filter by market condition_id. Leave empty for all markets.",
    )


class GetOrders(PolymarketBaseTool):
    """Get open orders for the agent's wallet on Polymarket.

    Shows all pending/open orders with prices, sizes, and order details.
    """

    name: str = "polymarket_get_orders"
    description: str = (
        "Get open orders on Polymarket for the agent's wallet. "
        "Optionally filter by market condition_id. "
        "Shows order details including side, price, size, and status."
    )
    args_schema: ArgsSchema | None = GetOrdersInput
    price: Decimal = Decimal("5")

    async def _arun(
        self,
        market: str | None = None,
        **kwargs: Any,
    ) -> str:
        self._require_wallet("view orders")

        await self.user_rate_limit_by_skill(limit=30, seconds=60)

        params: dict[str, Any] = {}
        if market:
            params["market"] = market

        data = await self._clob_auth_get("/orders", params=params)

        raw_orders: list[Any] = (
            data if isinstance(data, list) else data.get("orders", [])
        )
        formatted = []
        for order in raw_orders:
            if not isinstance(order, dict):
                continue
            formatted.append(
                {
                    "order_id": order.get("id", order.get("orderID", "")),
                    "market": order.get("market", ""),
                    "token_id": order.get("asset_id", order.get("tokenId", "")),
                    "side": order.get("side", ""),
                    "price": order.get("price", ""),
                    "original_size": order.get("original_size", order.get("size", "")),
                    "remaining_size": order.get(
                        "size_matched",
                        order.get("remainingSize", ""),
                    ),
                    "status": order.get("status", ""),
                    "created_at": order.get("created_at", order.get("createdAt", "")),
                    "order_type": order.get("type", order.get("orderType", "")),
                }
            )

        return json.dumps(
            {
                "orders": formatted,
                "count": len(formatted),
            }
        )
