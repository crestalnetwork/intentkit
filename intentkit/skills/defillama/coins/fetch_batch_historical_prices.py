"""Tool for fetching batch historical token prices via DeFi Llama API."""

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_batch_historical_prices
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_BATCH_HISTORICAL_PRICES_PROMPT = """Fetch historical prices for multiple tokens at multiple timestamps via DefiLlama. Token format: 'chain:address' or 'coingecko:id'."""


class HistoricalPricePoint(BaseModel):
    """Model representing a single historical price point."""

    timestamp: int = Field(..., description="Unix timestamp")
    price: float = Field(..., description="Price in USD")
    confidence: float = Field(..., description="Confidence score")


class TokenPriceHistory(BaseModel):
    """Model representing historical price data for a single token."""

    symbol: str = Field(..., description="Symbol")
    prices: list[HistoricalPricePoint] = Field(..., description="Price points")


class FetchBatchHistoricalPricesInput(BaseModel):
    """Input schema for fetching batch historical token prices."""

    coins_timestamps: dict[str, list[int]] = Field(
        ..., description="Map of token ID to list of unix timestamps"
    )


class FetchBatchHistoricalPricesResponse(BaseModel):
    """Response schema for batch historical token prices."""

    coins: dict[str, TokenPriceHistory] = Field(
        default_factory=dict, description="Prices by token ID"
    )
    error: str | None = Field(None, description="Error message")


class DefiLlamaFetchBatchHistoricalPrices(DefiLlamaBaseTool):
    """Tool for fetching batch historical token prices from DeFi Llama.

    This tool retrieves historical prices for multiple tokens at multiple
    timestamps, using a 4-hour search window around each requested time.

    Example:
        prices_tool = DefiLlamaFetchBatchHistoricalPrices(
            ,
            agent_id="agent_123",
            agent=agent
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
    args_schema: ArgsSchema | None = FetchBatchHistoricalPricesInput

    async def _arun(
        self, coins_timestamps: dict[str, list[int]]
    ) -> FetchBatchHistoricalPricesResponse:
        """Fetch historical prices for the given tokens at specified timestamps.

        Args:
            config: Runnable configuration
            coins_timestamps: Dictionary mapping token identifiers to lists of timestamps

        Returns:
            FetchBatchHistoricalPricesResponse containing historical token prices or error
        """
        # Check rate limiting
        context = self.get_context()
        is_rate_limited, error_msg = await self.check_rate_limit(context)
        if is_rate_limited:
            raise ToolException(error_msg)

        # Fetch batch historical prices from API
        result = await fetch_batch_historical_prices(coins_timestamps=coins_timestamps)

        # Return the response matching the API structure
        return FetchBatchHistoricalPricesResponse(coins=result["coins"])
