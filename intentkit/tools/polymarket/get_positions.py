"""Polymarket tool: get current positions."""

import json
from decimal import Decimal
from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.tools.onchain import WALLET_ADDRESS_ARG_DESCRIPTION
from intentkit.tools.polymarket.base import PolymarketBaseTool


class GetPositionsInput(BaseModel):
    """Input for getting positions."""

    wallet_address: str = Field(description=WALLET_ADDRESS_ARG_DESCRIPTION)


class GetPositions(PolymarketBaseTool):
    """Get the current Polymarket positions (holdings).

    Shows all outcome tokens held, their quantities, and current values.
    """

    name: str = "polymarket_get_positions"
    title: str = "Get Positions"
    description: str = (
        "Get current Polymarket positions (holdings). "
        "Shows all outcome tokens held with quantities and current market values."
    )
    args_schema: ArgsSchema | None = GetPositionsInput
    price: Decimal = Decimal("5")

    async def _arun(self, wallet_address: str, **kwargs: Any) -> str:
        await self.user_rate_limit_by_tool(limit=30, seconds=60)

        # Read-only: validate team ownership, then query the public data API
        # with the wallet's on-chain (funds-holder) address.
        wallet = await self.resolve_wallet(wallet_address)
        holder_address = wallet.evm_wallet_address or wallet_address

        positions = await self._data_get("/positions", params={"user": holder_address})

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
