import httpx
from typing import Type
from pydantic import BaseModel, Field
from skills.coingecko.base import CoinGeckoBaseTool


class PriceCheckerInput(BaseModel):
    """Input for the CryptoPriceChecker skill."""
    coin_id: str = Field(description="ID of the cryptocurrency (e.g., bitcoin, ethereum)")
    vs_currency: str = Field(description="Comparison currency (e.g., usd, idr)", default="usd")


class CryptoPriceChecker(CoinGeckoBaseTool):
    """Fetches current price, market cap, and other data for a cryptocurrency from CoinGecko API."""

    name: str = "crypto_price_checker"
    description: str = (
        "Fetches the current price, market capitalization, 24-hour trading volume, and 24-hour price change "
        "for a specific cryptocurrency using the CoinGecko API. "
        "Use this skill when a user requests crypto price data, e.g., 'What is the price of Bitcoin?' "
        "or 'What is Ethereum's market cap in IDR?'."
    )
    args_schema: Type[BaseModel] = PriceCheckerInput

    async def _arun(self, coin_id: str, vs_currency: str = "usd", **kwargs) -> str:
        """Fetches crypto price data from CoinGecko API."""
        base_url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": coin_id,
            "vs_currencies": vs_currency,
            "include_market_cap": "true",
            "include_24hr_vol": "true",
            "include_24hr_change": "true",
            "include_last_updated_at": "true",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(base_url, params=params)
                response.raise_for_status()  # Raise error if status code is not 200
                data = response.json()

                # Check if coin is found
                if coin_id not in data:
                    return f"Error: Coin '{coin_id}' not found. Try using IDs like 'bitcoin' or 'ethereum'."

                # Extract data
                coin_data = data[coin_id]
                price = coin_data.get(vs_currency, "Not available")
                market_cap = coin_data.get(f"{vs_currency}_market_cap", "Not available")
                volume_24h = coin_data.get(f"{vs_currency}_24h_vol", "Not available")
                change_24h = coin_data.get(f"{vs_currency}_24h_change", "Not available")
                last_updated = coin_data.get("last_updated_at", "Not available")

                # Format output
                output = (
                    f"Data for {coin_id.upper()} ({vs_currency.upper()}):\n"
                    f"- Price: {price}\n"
                    f"- Market Cap: {market_cap}\n"
                    f"- 24h Volume: {volume_24h}\n"
                    f"- 24h Price Change: {change_24h}%\n"
                    f"- Last Updated: {last_updated} (timestamp)"
                )
                return output
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return f"Error: Coin '{coin_id}' not found on CoinGecko."
            elif e.response.status_code == 429:
                return "Error: CoinGecko API rate limit reached. Try again later."
            return f"Error: Failed to fetch data. Status: {e.response.status_code}"
        except Exception as e:
            return f"Error: An issue occurred while fetching data: {str(e)}"
