"""Polymarket skill: search and browse prediction markets."""

import json
from decimal import Decimal
from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.polymarket.base import PolymarketBaseTool


def _format_market_summary(market: dict[str, Any]) -> dict[str, Any]:
    """Extract a summary dict from a Gamma API market object."""
    return {
        "condition_id": market.get("conditionId", ""),
        "question": market.get("question", ""),
        "description": (market.get("description") or "")[:200],
        "outcome_prices": market.get("outcomePrices", ""),
        "outcomes": market.get("outcomes", ""),
        "volume_24h": market.get("volume24hr", 0),
        "liquidity": market.get("liquidity", 0),
        "end_date": market.get("endDate", ""),
        "active": market.get("active", False),
    }


class SearchMarketsInput(BaseModel):
    """Input for searching Polymarket markets."""

    query: str | None = Field(
        default=None,
        description="Search query text to filter markets by title or description",
    )
    tag: str | None = Field(
        default=None,
        description="Filter by tag (e.g. 'politics', 'crypto', 'sports')",
    )
    active: bool = Field(
        default=True,
        description="If true, only return active (open) markets",
    )
    limit: int = Field(
        default=10,
        description="Maximum number of markets to return (1-50)",
        ge=1,
        le=50,
    )


class SearchMarkets(PolymarketBaseTool):
    """Search and browse Polymarket prediction markets.

    Returns a list of markets matching the query, with titles,
    descriptions, current prices (probabilities), and trading volumes.
    """

    name: str = "polymarket_search_markets"
    description: str = (
        "Search Polymarket prediction markets by keyword or tag. "
        "Returns market titles, current probabilities, and trading volumes. "
        "Use this to discover markets on topics of interest."
    )
    args_schema: ArgsSchema | None = SearchMarketsInput
    price: Decimal = Decimal("1")

    async def _arun(
        self,
        query: str | None = None,
        tag: str | None = None,
        active: bool = True,
        limit: int = 10,
        **kwargs: Any,
    ) -> str:
        await self.global_rate_limit_by_skill(limit=300, seconds=60)

        params: dict[str, Any] = {
            "limit": min(limit, 50),
            "order": "volume24hr",
            "ascending": "false",
        }
        if active:
            params["active"] = "true"
        if tag:
            params["tag"] = tag

        results: list[dict[str, Any]] = []

        if query:
            params["_q"] = query
            data = await self._gamma_get("/events", params=params)
            events = data if isinstance(data, list) else []
            for event in events[:limit]:
                if not isinstance(event, dict):
                    continue
                markets = event.get("markets", [])
                for market in markets:
                    if isinstance(market, dict):
                        results.append(_format_market_summary(market))
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break
        else:
            data = await self._gamma_get("/markets", params=params)
            markets_list = data if isinstance(data, list) else []
            for market in markets_list[:limit]:
                if isinstance(market, dict):
                    results.append(_format_market_summary(market))

        return json.dumps({"markets": results, "count": len(results)})
