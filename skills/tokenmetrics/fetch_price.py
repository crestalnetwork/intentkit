"""Skill to fetch current price for BTC or ETH from TokenMetrics API."""

from typing import Literal, Type

import httpx
from langchain.tools.base import ToolException
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from .base import TokenMetricsBaseTool, base_url


class TokenMetricsPriceInput(BaseModel):
    """Input schema for fetching price."""

    token_symbol: Literal["BTC", "ETH"] = Field(description="Token symbol (BTC or ETH)")


class PriceData(BaseModel):
    """Data model for price response."""

    token_id: int = Field(description="Token ID")
    current_price: float = Field(description="Current price in USD")
    token_name: str = Field(description="Token name")
    token_symbol: str = Field(description="Token symbol")


class TokenMetricsPriceOutput(BaseModel):
    """Output schema for fetching price."""

    data: PriceData
    summary: str = Field(description="Summary of the price data")


class FetchPrice(TokenMetricsBaseTool):
    """Skill to fetch the current price for BTC or ETH from TokenMetrics API."""

    name: str = "fetch_price"
    description: str = "Fetches the current price for BTC or ETH from TokenMetrics API."
    args_schema: Type[BaseModel] = TokenMetricsPriceInput

    async def fetch_price(self, token_symbol: str, api_key: str) -> PriceData:
        """Fetch the current price from TokenMetrics API.

        Args:
            token_symbol: Token symbol (BTC or ETH).
            api_key: TokenMetrics API key.

        Returns:
            PriceData containing the token's price and metadata.

        Raises:
            ToolException: If the API request fails or data is invalid.
        """
        token_id_map = {"BTC": 3375, "ETH": 3367}
        token_id = token_id_map.get(token_symbol)
        if not token_id:
            raise ToolException(f"Unsupported token symbol: {token_symbol}")

        url = f"{base_url}price?token_id={token_id}"
        headers = {"accept": "application/json", "api_key": api_key}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()["data"][0]
                return PriceData(
                    token_id=data["TOKEN_ID"],
                    current_price=data["CURRENT_PRICE"],
                    token_name=data["TOKEN_NAME"],
                    token_symbol=data["TOKEN_SYMBOL"],
                )
            except (httpx.RequestError, httpx.HTTPStatusError, KeyError) as e:
                raise ToolException(f"Error fetching price from TokenMetrics: {e}")

    async def _arun(self, token_symbol: str, config: RunnableConfig, **kwargs):
        """Async execution for fetching price.

        Args:
            token_symbol: Token symbol (BTC or ETH).
            config: Runnable configuration.
            **kwargs: Additional keyword arguments.

        Returns:
            TokenMetricsPriceOutput with price data and summary.

        Raises:
            ToolException: If the API key is missing or request fails.
        """
        context = self.context_from_config(config)
        api_key = self.get_api_key(context)
        if not api_key:
            raise ToolException("TokenMetrics API key not found")

        price_data = await self.fetch_price(token_symbol, api_key)
        summary = f"Current price for {price_data.token_name} ({token_symbol}): ${price_data.current_price:,.2f}"

        return TokenMetricsPriceOutput(data=price_data, summary=summary)

    def _run(self, question: str):
        raise NotImplementedError("Use _arun for async execution")
