"""Tool for fetching historical token prices via DeFi Llama API."""

from typing import Dict, List, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_historical_prices
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_HISTORICAL_PRICES_PROMPT = """
This tool fetches historical token prices from DeFi Llama for a specific timestamp.
Provide a timestamp and list of token identifiers in the format:
- Ethereum tokens: 'ethereum:0x...'
- Other chains: 'chainname:0x...'
- CoinGecko IDs: 'coingecko:bitcoin'
Returns historical price data including:
- Price in USD at the specified time
- Token symbol
- Token decimals (if available)
- Actual timestamp of the price data
Uses a 4-hour search window around the specified timestamp.
"""


class HistoricalTokenPrice(BaseModel):
    """Model representing historical token price data."""

    price: float = Field(..., description="Token price in USD at the specified time")
    symbol: Optional[str] = Field(None, description="Token symbol")
    timestamp: int = Field(..., description="Unix timestamp of the price data")
    decimals: Optional[int] = Field(None, description="Token decimals, if available")


class FetchHistoricalPricesInput(BaseModel):
    """Input schema for fetching historical token prices."""

    timestamp: int = Field(
        ..., description="Unix timestamp for historical price lookup"
    )
    coins: List[str] = Field(
        ...,
        description="List of token identifiers (e.g. 'ethereum:0x...', 'coingecko:ethereum')",
    )


class FetchHistoricalPricesResponse(BaseModel):
    """Response schema for historical token prices."""

    coins: Dict[str, HistoricalTokenPrice] = Field(
        default_factory=dict,
        description="Historical token prices keyed by token identifier",
    )
    error: Optional[str] = Field(None, description="Error message if any")


class DefiLlamaFetchHistoricalPrices(DefiLlamaBaseTool):
    """Tool for fetching historical token prices from DeFi Llama.

    This tool retrieves historical prices for multiple tokens at a specific
    timestamp, using a 4-hour search window around the requested time.

    Example:
        prices_tool = DefiLlamaFetchHistoricalPrices(
            skill_store=store,
            agent_id="agent_123",
            agent_store=agent_store
        )
        result = await prices_tool._arun(
            timestamp=1640995200,  # Jan 1, 2022
            coins=["ethereum:0x...", "coingecko:bitcoin"]
        )
    """

    name: str = "defillama_fetch_historical_prices"
    description: str = FETCH_HISTORICAL_PRICES_PROMPT
    args_schema: Type[BaseModel] = FetchHistoricalPricesInput

    async def _arun(
        self, timestamp: int, coins: List[str]
    ) -> FetchHistoricalPricesResponse:
        """Fetch historical prices for the given tokens at the specified time.

        Args:
            config: Runnable configuration
            timestamp: Unix timestamp for historical price lookup
            coins: List of token identifiers to fetch prices for

        Returns:
            FetchHistoricalPricesResponse containing historical token prices or error
        """
        try:
            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return FetchHistoricalPricesResponse(error=error_msg)

            # Fetch historical prices from API
            result = await fetch_historical_prices(timestamp=timestamp, coins=coins)

            # Check for API errors
            if isinstance(result, dict) and "error" in result:
                return FetchHistoricalPricesResponse(error=result["error"])

            # Return the response matching the API structure
            return FetchHistoricalPricesResponse(coins=result["coins"])

        except Exception as e:
            return FetchHistoricalPricesResponse(error=str(e))
