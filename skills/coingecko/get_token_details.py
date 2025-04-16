from pydantic import BaseModel, Field
from typing import Optional
from .base import CoinGeckoBaseTool
import httpx

class TokenDetailsInput(BaseModel):
    coin_id: str = Field(description="CoinGecko coin ID (e.g.: 'bitcoin')")
    currency: str = Field(default="usd", description="Target currency")

class GetTokenDetails(CoinGeckoBaseTool):
    name: str = "get_token_details"
    description: str = (
        "Fetch detailed market data for a cryptocurrency from CoinGecko.\n"
        "Includes price, volume, market cap, and price changes."
    )
    args_schema: Type[BaseModel] = TokenDetailsInput

    async def _arun(self, coin_id: str, currency: str = "usd", **kwargs) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_base}/coins/{coin_id}",
                params={"localization": "false", "tickers": "false"}
            )
            response.raise_for_status()
            data = response.json()
            
            market_data = data["market_data"]
            return {
                "name": data["name"],
                "symbol": data["symbol"],
                "current_price": market_data[f"current_price_{currency}"],
                "market_cap": market_data[f"market_cap_{currency}"],
                "24h_high": market_data[f"high_24h_{currency}"],
                "24h_low": market_data[f"low_24h_{currency}"],
                "24h_volume": market_data[f"total_volume_{currency}"],
                "price_change_24h": market_data["price_change_24h_in_currency"][currency],
                "last_updated": data["last_updated"]
            }
