"""Tool for fetching token price charts via DeFi Llama API."""

from typing import Dict, List, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_price_chart
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_PRICE_CHART_PROMPT = """
This tool fetches price chart data from DeFi Llama for multiple tokens.
Provide a list of token identifiers in the format:
- Ethereum tokens: 'ethereum:0x...'
- Other chains: 'chainname:0x...'
- CoinGecko IDs: 'coingecko:bitcoin'
Returns price chart data including:
- Historical price points for the last 24 hours
- Token symbol and metadata
- Confidence scores for price data
- Token decimals (if available)
"""


class PricePoint(BaseModel):
    """Model representing a single price point in the chart."""

    timestamp: int = Field(..., description="Unix timestamp of the price data")
    price: float = Field(..., description="Token price in USD at the timestamp")


class TokenPriceChart(BaseModel):
    """Model representing price chart data for a single token."""

    symbol: str = Field(..., description="Token symbol")
    confidence: float = Field(..., description="Confidence score for the price data")
    decimals: Optional[int] = Field(None, description="Token decimals")
    prices: List[PricePoint] = Field(..., description="List of historical price points")


class FetchPriceChartInput(BaseModel):
    """Input schema for fetching token price charts."""

    coins: List[str] = Field(
        ..., description="List of token identifiers to fetch price charts for"
    )


class FetchPriceChartResponse(BaseModel):
    """Response schema for token price charts."""

    coins: Dict[str, TokenPriceChart] = Field(
        default_factory=dict, description="Price chart data keyed by token identifier"
    )
    error: Optional[str] = Field(None, description="Error message if any")


class DefiLlamaFetchPriceChart(DefiLlamaBaseTool):
    """Tool for fetching token price charts from DeFi Llama.

    This tool retrieves price chart data for multiple tokens over the last 24 hours,
    including historical price points and token metadata.

    Example:
        chart_tool = DefiLlamaFetchPriceChart(
            skill_store=store,
            agent_id="agent_123",
            agent_store=agent_store
        )
        result = await chart_tool._arun(
            coins=["ethereum:0x...", "coingecko:ethereum"]
        )
    """

    name: str = "defillama_fetch_price_chart"
    description: str = FETCH_PRICE_CHART_PROMPT
    args_schema: Type[BaseModel] = FetchPriceChartInput

    async def _arun(self, coins: List[str]) -> FetchPriceChartResponse:
        """Fetch price charts for the given tokens.

        Args:
            config: Runnable configuration
            coins: List of token identifiers to fetch price charts for

        Returns:
            FetchPriceChartResponse containing price chart data or error
        """
        try:
            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return FetchPriceChartResponse(error=error_msg)

            # Fetch price chart data from API
            result = await fetch_price_chart(coins=coins)

            # Check for API errors
            if isinstance(result, dict) and "error" in result:
                return FetchPriceChartResponse(error=result["error"])

            # Return the response matching the API structure
            return FetchPriceChartResponse(coins=result["coins"])

        except Exception as e:
            return FetchPriceChartResponse(error=str(e))
