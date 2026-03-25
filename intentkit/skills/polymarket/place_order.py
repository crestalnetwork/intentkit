"""Polymarket skill: place a buy or sell order."""

import json
import logging
from decimal import Decimal
from typing import Any, Literal

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.polymarket.base import BUY, PolymarketBaseTool

logger = logging.getLogger(__name__)


class PlaceOrderInput(BaseModel):
    """Input for placing an order."""

    token_id: str = Field(
        description=(
            "The token ID of the outcome to trade. "
            "Get token IDs from the get_market skill."
        ),
    )
    side: Literal["BUY", "SELL"] = Field(
        description="Order side: 'BUY' to buy outcome tokens, 'SELL' to sell",
    )
    price: float = Field(
        description=(
            "Price per share between 0 and 1 (exclusive). "
            "Represents the probability you're willing to pay/receive. "
            "E.g. 0.65 means 65 cents per share."
        ),
        gt=0,
        lt=1,
    )
    size: float = Field(
        description="Number of shares to buy or sell",
        gt=0,
    )
    neg_risk: bool = Field(
        default=False,
        description="Set to true for negative risk markets (multi-outcome events)",
    )


class PlaceOrder(PolymarketBaseTool):
    """Place a limit order on a Polymarket outcome token.

    Requires a configured wallet with signing capabilities.
    The order will be placed on the CLOB (Central Limit Order Book).
    """

    name: str = "polymarket_place_order"
    description: str = (
        "Place a limit order to buy or sell Polymarket outcome tokens. "
        "Specify the token_id, side (BUY/SELL), price (0-1), and size. "
        "Price represents the probability - e.g. price=0.60 means you pay "
        "$0.60 per share. If the outcome resolves YES, each share pays $1. "
        "IMPORTANT: Ensure you have sufficient USDC balance on Polygon."
    )
    args_schema: ArgsSchema | None = PlaceOrderInput
    price: Decimal = Decimal("100")

    async def _arun(
        self,
        token_id: str,
        side: str,
        price: float,
        size: float,
        neg_risk: bool = False,
        **kwargs: Any,
    ) -> str:
        self._require_wallet("place orders")

        await self.user_rate_limit_by_skill(limit=10, seconds=60)

        side_int = BUY if side.upper() == "BUY" else 1

        tick_size = "0.01"
        try:
            tick_data = await self._clob_get(f"/tick-size/{token_id}")
            tick_size = str(tick_data.get("minimum_tick_size", "0.01"))
        except Exception:
            logger.warning("Failed to get tick size for %s, using default", token_id)

        order_payload = await self._sign_order(
            token_id=token_id,
            side=side_int,
            price=price,
            size=size,
            tick_size=tick_size,
            neg_risk=neg_risk,
        )

        # Post the order
        result = await self._clob_auth_post("/order", order_payload)

        return json.dumps(
            {
                "success": True,
                "order_id": result.get("orderID", result.get("id", "")),
                "status": result.get("status", ""),
                "side": side.upper(),
                "price": price,
                "size": size,
                "token_id": token_id,
            }
        )
