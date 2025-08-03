"""Tool for fetching batch historical token prices via DeFi Llama API."""

from typing import Dict, List, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_batch_historical_prices
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_BATCH_HISTORICAL_PRICES_PROMPT = """
This tool fetches historical token prices from DeFi Llama for multiple tokens at multiple timestamps.
Provide a dictionary mapping token identifiers to lists of timestamps in the format:
- Ethereum tokens: {"ethereum:0x...": [timestamp1, timestamp2]}
- Other chains: {"chainname:0x...": [timestamp1, timestamp2]}
- CoinGecko IDs: {"coingecko:bitcoin": [timestamp1, timestamp2]}
Returns historical price data including:
- Prices in USD at each timestamp
- Token symbols
- Confidence scores for price data
Uses a 4-hour search window around each specified timestamp.
"""


class HistoricalPricePoint(BaseModel):
    """Model representing a single historical price point."""

    timestamp: int = Field(..., description="Unix timestamp of the price data")
    price: float = Field(..., description="Token price in USD at the timestamp")
    confidence: float = Field(..., description="Confidence score for the price data")


class TokenPriceHistory(BaseModel):
    """Model representing historical price data for a single token."""

    symbol: str = Field(..., description="Token symbol")
    prices: List[HistoricalPricePoint] = Field(
        ..., description="List of historical price points"
    )


class FetchBatchHistoricalPricesInput(BaseModel):
    """Input schema for fetching batch historical token prices."""

    coins_timestamps: Dict[str, List[int]] = Field(
        ..., description="Dictionary mapping token identifiers to lists of timestamps"
    )


class FetchBatchHistoricalPricesResponse(BaseModel):
    """Response schema for batch historical token prices."""

    coins: Dict[str, TokenPriceHistory] = Field(
        default_factory=dict,
        description="Historical token prices keyed by token identifier",
    )
    error: Optional[str] = Field(None, description="Error message if any")


class DefiLlamaFetchBatchHistoricalPrices(DefiLlamaBaseTool):
    """Tool for fetching batch historical token prices from DeFi Llama.

    This tool retrieves historical prices for multiple tokens at multiple
    timestamps, using a 4-hour search window around each requested time.

    Example:
        prices_tool = DefiLlamaFetchBatchHistoricalPrices(
            skill_store=store,
            agent_id="agent_123",
            agent_store=agent_store
        )
        result = await prices_tool._arun(
            coins_timestamps={
                "ethereum:0x...": [1640995200, 1641081600],  # Jan 1-2, 2022
                "coingecko:bitcoin": [1640995200, 1641081600]
            }
        )
    """

    name: str = "defillama_fetch_batch_historical_prices"
    description: str = FETCH_BATCH_HISTORICAL_PRICES_PROMPT
    args_schema: Type[BaseModel] = FetchBatchHistoricalPricesInput

    async def _arun(
        self, coins_timestamps: Dict[str, List[int]]
    ) -> FetchBatchHistoricalPricesResponse:
        """Fetch historical prices for the given tokens at specified timestamps.

        Args:
            config: Runnable configuration
            coins_timestamps: Dictionary mapping token identifiers to lists of timestamps

        Returns:
            FetchBatchHistoricalPricesResponse containing historical token prices or error
        """
        try:
            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return FetchBatchHistoricalPricesResponse(error=error_msg)

            # Fetch batch historical prices from API
            result = await fetch_batch_historical_prices(
                coins_timestamps=coins_timestamps
            )

            # Check for API errors
            if isinstance(result, dict) and "error" in result:
                return FetchBatchHistoricalPricesResponse(error=result["error"])

            # Return the response matching the API structure
            return FetchBatchHistoricalPricesResponse(coins=result["coins"])

        except Exception as e:
            return FetchBatchHistoricalPricesResponse(error=str(e))
