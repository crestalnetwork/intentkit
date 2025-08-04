"""Tool for fetching first recorded token prices via DeFi Llama API."""

from typing import Dict, List, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_first_price
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_FIRST_PRICE_PROMPT = """
This tool fetches the first recorded price data from DeFi Llama for multiple tokens.
Provide a list of token identifiers in the format:
- Ethereum tokens: 'ethereum:0x...'
- Other chains: 'chainname:0x...'
- CoinGecko IDs: 'coingecko:bitcoin'
Returns first price data including:
- Initial price in USD
- Token symbol
- Timestamp of first recorded price
"""


class FirstPriceData(BaseModel):
    """Model representing first price data for a single token."""

    symbol: str = Field(..., description="Token symbol")
    price: float = Field(..., description="First recorded price in USD")
    timestamp: int = Field(..., description="Unix timestamp of first recorded price")


class FetchFirstPriceInput(BaseModel):
    """Input schema for fetching first token prices."""

    coins: List[str] = Field(
        ..., description="List of token identifiers to fetch first prices for"
    )


class FetchFirstPriceResponse(BaseModel):
    """Response schema for first token prices."""

    coins: Dict[str, FirstPriceData] = Field(
        default_factory=dict, description="First price data keyed by token identifier"
    )
    error: Optional[str] = Field(None, description="Error message if any")


class DefiLlamaFetchFirstPrice(DefiLlamaBaseTool):
    """Tool for fetching first recorded token prices from DeFi Llama.

    This tool retrieves the first price data recorded for multiple tokens,
    including the initial price, symbol, and timestamp.

    Example:
        first_price_tool = DefiLlamaFetchFirstPrice(
            skill_store=store,
            agent_id="agent_123",
            agent_store=agent_store
        )
        result = await first_price_tool._arun(
            coins=["ethereum:0x...", "coingecko:ethereum"]
        )
    """

    name: str = "defillama_fetch_first_price"
    description: str = FETCH_FIRST_PRICE_PROMPT
    args_schema: Type[BaseModel] = FetchFirstPriceInput

    async def _arun(self, coins: List[str]) -> FetchFirstPriceResponse:
        """Fetch first recorded prices for the given tokens.

        Args:
            config: Runnable configuration
            coins: List of token identifiers to fetch first prices for

        Returns:
            FetchFirstPriceResponse containing first price data or error
        """
        try:
            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return FetchFirstPriceResponse(error=error_msg)

            # Fetch first price data from API
            result = await fetch_first_price(coins=coins)

            # Check for API errors
            if isinstance(result, dict) and "error" in result:
                return FetchFirstPriceResponse(error=result["error"])

            # Return the response matching the API structure
            return FetchFirstPriceResponse(coins=result["coins"])

        except Exception as e:
            return FetchFirstPriceResponse(error=str(e))
