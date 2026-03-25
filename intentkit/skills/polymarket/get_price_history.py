"""Polymarket skill: get historical price data."""

import json
from decimal import Decimal
from typing import Any, Literal

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.polymarket.base import PolymarketBaseTool


class GetPriceHistoryInput(BaseModel):
    """Input for getting price history."""

    token_id: str = Field(
        description=(
            "The token ID of the outcome to get price history for. "
            "Get token IDs from the get_market skill."
        ),
    )
    interval: Literal["1h", "1d", "1w", "1m", "all"] = Field(
        default="1d",
        description="Time interval for price history",
    )
    fidelity: int = Field(
        default=60,
        description="Number of data points to return (1-500)",
        ge=1,
        le=500,
    )


class GetPriceHistory(PolymarketBaseTool):
    """Get historical price data for a Polymarket outcome token.

    Returns time-series price data for charting or analysis.
    Prices represent the implied probability (0 to 1) over time.
    """

    name: str = "polymarket_get_price_history"
    description: str = (
        "Get historical price data for a Polymarket outcome token. "
        "Returns time-series data showing how the probability has changed. "
        "Useful for analyzing trends and making informed trading decisions."
    )
    args_schema: ArgsSchema | None = GetPriceHistoryInput
    price: Decimal = Decimal("2")

    async def _arun(
        self,
        token_id: str,
        interval: str = "1d",
        fidelity: int = 60,
        **kwargs: Any,
    ) -> str:
        await self.global_rate_limit_by_skill(limit=300, seconds=60)

        # Map user-friendly intervals to API parameters
        interval_map = {
            "1h": "1h",
            "1d": "1d",
            "1w": "1w",
            "1m": "1m",
            "all": "max",
        }
        api_interval = interval_map.get(interval, interval)

        params: dict[str, Any] = {
            "token_id": token_id,
            "interval": api_interval,
            "fidelity": min(fidelity, 500),
        }

        data = await self._clob_get("/prices-history", params=params)

        # data is typically a list of {t: timestamp, p: price}
        history = data.get("history", data) if isinstance(data, dict) else data
        points = []
        if isinstance(history, list):
            for point in history:
                if isinstance(point, dict):
                    points.append(
                        {
                            "timestamp": point.get("t", ""),
                            "price": point.get("p", ""),
                        }
                    )

        result: dict[str, Any] = {
            "token_id": token_id,
            "interval": interval,
            "data_points": len(points),
            "history": points,
        }

        # Add summary stats
        if points:
            prices = [float(p["price"]) for p in points if p["price"] not in ("", None)]
            if prices:
                result["summary"] = {
                    "current": prices[-1],
                    "high": max(prices),
                    "low": min(prices),
                    "change": round(prices[-1] - prices[0], 4),
                }

        return json.dumps(result)
