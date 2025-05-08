import logging
from typing import Type

import httpx
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from skills.cookiefun.base import CookieFunBaseTool

logger = logging.getLogger(__name__)


class GetCryptoInput(BaseModel):
    """Input for GetCrypto tool."""

    crypto: str = Field(
        description="Name or symbol of the cryptocurrency (e.g. 'bitcoin' or 'btc')"
    )


class GetCrypto(CookieFunBaseTool):
    """Tool for getting cryptocurrency information from Cookie.fun."""

    name: str = "cookiefun_get_crypto"
    description: str = (
        "Get detailed information about a specific cryptocurrency including price, "
        "market cap, trading volume, and other metrics.\n"
        "Use this when you need information about a cryptocurrency."
    )
    args_schema: Type[BaseModel] = GetCryptoInput

    async def _arun(self, crypto: str, config: RunnableConfig = None, **kwargs) -> str:
        """Get cryptocurrency information from Cookie.fun API."""
        context = self.context_from_config(config)
        api_key = context.config.get("api_key")
        if not api_key:
            return "Error: Cookie.fun API key not configured"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.cookie-api.com/api/crypto",
                    params={"crypto": crypto},
                    headers={"Authorization": api_key},
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

                # Format the response in a readable way
                result = [
                    f"{data['name']} ({data['symbol'].upper()})",
                    f"Current Price: ${data['current_price_usd']:,.2f}",
                    f"24h Range: ${data['low_24h']:,.2f} - ${data['high_24h']:,.2f}",
                    f"Market Cap: ${data['market_cap']:,.2f}",
                    f"Trading Volume (24h): ${data['trading_volume']:,.2f}",
                    f"Circulating Supply: {data['circulating_supply']:,.2f}",
                    f"Total Supply: {data['total_supply']:,.2f}",
                    f"All Time High: ${data['all_time_high']:,.2f}",
                    f"All Time Low: ${data['all_time_low']:,.2f}",
                    "",
                    "Description:",
                    data["description"],
                ]

                return "\n".join(result)

        except httpx.HTTPError as e:
            logger.error(f"HTTP error when fetching crypto info: {str(e)}")
            return f"Error fetching cryptocurrency data: {str(e)}"
        except Exception as e:
            logger.error(f"Error getting crypto info: {str(e)}")
            return f"Unexpected error: {str(e)}"
