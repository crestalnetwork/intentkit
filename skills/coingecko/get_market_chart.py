from pydantic import BaseModel, Field
from typing import Type
from .base import CoinGeckoBaseTool
import httpx

class MarketChartInput(BaseModel):
    coin_id: str = Field(description="CoinGecko coin ID")
    currency: str = Field(default="usd", description="Target currency")
    days: int = Field(default=7, description="Days of historical data")

class GetMarketChart(CoinGeckoBaseTool):
    name: str = "get_market_chart"
    description: str = (
        "Fetch historical market data for a cryptocurrency.\n"
        "Returns price, market cap, and volume data over time."
    )
    args_schema: Type[BaseModel] = MarketChartInput

    async def _arun(self, coin_id: str, currency: str = "usd", days: int = 7, **kwargs) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_base}/coins/{coin_id}/market_chart",
                params={
                    "vs_currency": currency,
                    "days": days,
                    "interval": "daily"
                }
            )
            response.raise_for_status()
            return response.json()
