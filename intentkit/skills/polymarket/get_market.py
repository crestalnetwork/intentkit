"""Polymarket skill: get detailed market information."""

import asyncio
import json
from decimal import Decimal
from typing import Any

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.polymarket.base import PolymarketBaseTool


class GetMarketInput(BaseModel):
    """Input for getting market details."""

    market_id: str = Field(
        description=(
            "Market identifier: condition_id (hex string) or market slug. "
            "Use condition_id from search results for best accuracy."
        ),
    )


class GetMarket(PolymarketBaseTool):
    """Get detailed information about a specific Polymarket market.

    Returns full market details including description, outcome tokens,
    current probabilities, trading volume, and end date.
    """

    name: str = "polymarket_get_market"
    description: str = (
        "Get detailed information about a specific Polymarket prediction market. "
        "Provide a condition_id or slug. Returns market description, current "
        "probabilities for each outcome, token IDs needed for trading, "
        "volume, liquidity, and resolution details."
    )
    args_schema: ArgsSchema | None = GetMarketInput
    price: Decimal = Decimal("2")

    async def _fetch_midpoint(self, token_id: str) -> tuple[str, str]:
        """Fetch midpoint price for a single token, returning (token_id, price)."""
        try:
            price_data = await self._clob_get(
                "/midpoint", params={"token_id": token_id}
            )
            return (token_id, price_data.get("mid", "N/A"))
        except Exception:
            return (token_id, "N/A")

    async def _arun(self, market_id: str, **kwargs: Any) -> str:
        await self.global_rate_limit_by_skill(limit=300, seconds=60)

        # Try condition_id lookup first, then slug, then search
        market = None
        for path in [
            f"/markets/{market_id}",
            f"/markets/slug/{market_id}",
        ]:
            try:
                result = await self._gamma_get(path)
                if result and isinstance(result, dict) and result.get("conditionId"):
                    market = result
                    break
            except Exception:
                continue

        if not market:
            # Fallback: search by condition_id as query param
            results = await self._gamma_get(
                "/markets", params={"condition_id": market_id, "limit": 1}
            )
            if isinstance(results, list) and results:
                market = results[0]

        if not market:
            raise ToolException(f"Market not found: {market_id}")

        tokens = market.get("clobTokenIds", "")
        if isinstance(tokens, str):
            try:
                tokens = json.loads(tokens) if tokens else []
            except json.JSONDecodeError:
                tokens = []

        # Fetch midpoint prices concurrently
        price_results = await asyncio.gather(
            *(self._fetch_midpoint(tid) for tid in tokens)
        )
        token_prices = dict(price_results)

        outcomes = market.get("outcomes", "")
        if isinstance(outcomes, str):
            try:
                outcomes = json.loads(outcomes) if outcomes else []
            except json.JSONDecodeError:
                outcomes = []

        result = {
            "condition_id": market.get("conditionId", ""),
            "question": market.get("question", ""),
            "description": market.get("description", ""),
            "outcomes": outcomes,
            "outcome_prices": market.get("outcomePrices", ""),
            "tokens": [
                {"token_id": tid, "midpoint_price": token_prices.get(tid, "N/A")}
                for tid in tokens
            ],
            "volume_24h": market.get("volume24hr", 0),
            "total_volume": market.get("volumeNum", 0),
            "liquidity": market.get("liquidity", 0),
            "end_date": market.get("endDate", ""),
            "active": market.get("active", False),
            "closed": market.get("closed", False),
            "neg_risk": market.get("negRisk", False),
            "market_slug": market.get("slug", ""),
        }

        return json.dumps(result)
