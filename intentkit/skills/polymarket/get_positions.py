"""Polymarket skill: get current positions."""

import json
from decimal import Decimal
from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel

from intentkit.skills.polymarket.base import PolymarketBaseTool


class GetPositionsInput(BaseModel):
    """Input for getting positions (no parameters needed)."""

    pass


class GetPositions(PolymarketBaseTool):
    """Get the current positions (holdings) for the agent's wallet.

    Shows all outcome tokens held, their quantities, and current values.
    """

    name: str = "polymarket_get_positions"
    description: str = (
        "Get current Polymarket positions (holdings) for the agent's wallet. "
        "Shows all outcome tokens held with quantities and current market values. "
        "No input needed - automatically uses the configured wallet address."
    )
    args_schema: ArgsSchema | None = GetPositionsInput
    price: Decimal = Decimal("5")

    async def _arun(self, **kwargs: Any) -> str:
        self._require_wallet("view positions")

        await self.user_rate_limit_by_skill(limit=30, seconds=60)

        wallet_address = await self.get_wallet_address()

        try:
            positions = await self._data_get(
                "/positions", params={"user": wallet_address}
            )
        except Exception:
            positions = await self._clob_auth_get(
                "/positions", params={"user": wallet_address}
            )

        if not positions:
            return json.dumps(
                {
                    "wallet_address": wallet_address,
                    "positions": [],
                    "message": "No open positions found",
                }
            )

        pos_list: list[Any] = positions if isinstance(positions, list) else [positions]
        formatted = []
        for pos in pos_list:
            if not isinstance(pos, dict):
                continue
            formatted.append(
                {
                    "market": pos.get("market", pos.get("conditionId", "")),
                    "token_id": pos.get("asset", pos.get("tokenId", "")),
                    "side": pos.get("side", ""),
                    "size": pos.get("size", pos.get("amount", 0)),
                    "avg_price": pos.get("avgPrice", ""),
                    "current_value": pos.get("currentValue", ""),
                    "pnl": pos.get("pnl", ""),
                }
            )

        return json.dumps(
            {
                "wallet_address": wallet_address,
                "positions": formatted,
                "count": len(formatted),
            }
        )
