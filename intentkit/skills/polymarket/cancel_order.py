"""Polymarket skill: cancel orders."""

import json
from decimal import Decimal
from typing import Any

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.polymarket.base import PolymarketBaseTool


class CancelOrderInput(BaseModel):
    """Input for canceling orders."""

    order_id: str | None = Field(
        default=None,
        description="ID of a specific order to cancel. Leave empty to cancel all.",
    )
    cancel_all: bool = Field(
        default=False,
        description="Set to true to cancel all open orders",
    )


class CancelOrder(PolymarketBaseTool):
    """Cancel one or all open orders on Polymarket.

    Can cancel a specific order by ID, or all open orders at once.
    """

    name: str = "polymarket_cancel_order"
    description: str = (
        "Cancel orders on Polymarket. Either provide an order_id to cancel "
        "a specific order, or set cancel_all=true to cancel all open orders."
    )
    args_schema: ArgsSchema | None = CancelOrderInput
    price: Decimal = Decimal("10")

    async def _arun(
        self,
        order_id: str | None = None,
        cancel_all: bool = False,
        **kwargs: Any,
    ) -> str:
        self._require_wallet("cancel orders")

        await self.user_rate_limit_by_skill(limit=20, seconds=60)

        if not order_id and not cancel_all:
            raise ToolException("Provide either an order_id or set cancel_all=true")

        if cancel_all:
            result = await self._clob_auth_delete("/cancel-all")
            return json.dumps(
                {
                    "success": True,
                    "action": "cancel_all",
                    "message": "All open orders have been canceled",
                    "details": result,
                }
            )
        else:
            result = await self._clob_auth_delete("/order", body={"orderID": order_id})
            return json.dumps(
                {
                    "success": True,
                    "action": "cancel_single",
                    "order_id": order_id,
                    "details": result,
                }
            )
