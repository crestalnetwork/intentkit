"""Tool for fetching token price charts via DeFi Llama API."""

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_price_chart
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_PRICE_CHART_PROMPT = """Fetch 24h price chart data for tokens via DefiLlama. Token format: 'chain:address' or 'coingecko:id'."""


class PricePoint(BaseModel):
    """Model representing a single price point in the chart."""

    timestamp: int = Field(..., description="Unix timestamp")
    price: float = Field(..., description="Price in USD")


class TokenPriceChart(BaseModel):
    """Model representing price chart data for a single token."""

    symbol: str = Field(..., description="Symbol")
    confidence: float = Field(..., description="Confidence score")
    decimals: int | None = Field(None, description="Decimals")
    prices: list[PricePoint] = Field(..., description="Price points")


class FetchPriceChartInput(BaseModel):
    """Input schema for fetching token price charts."""

    coins: list[str] = Field(..., description="Token IDs to query")


class FetchPriceChartResponse(BaseModel):
    """Response schema for token price charts."""

    coins: dict[str, TokenPriceChart] = Field(
        default_factory=dict, description="Charts by token ID"
    )
    error: str | None = Field(None, description="Error message")


class DefiLlamaFetchPriceChart(DefiLlamaBaseTool):
    """Tool for fetching token price charts from DeFi Llama.

    This tool retrieves price chart data for multiple tokens over the last 24 hours,
    including historical price points and token metadata.

    Example:
        chart_tool = DefiLlamaFetchPriceChart(
            ,
            agent_id="agent_123",
            agent=agent
        )
        result = await chart_tool._arun(
            coins=["ethereum:0x...", "coingecko:ethereum"]
        )
    """

    name: str = "defillama_fetch_price_chart"
    description: str = FETCH_PRICE_CHART_PROMPT
    args_schema: ArgsSchema | None = FetchPriceChartInput

    async def _arun(self, coins: list[str]) -> FetchPriceChartResponse:
        """Fetch price charts for the given tokens.

        Args:
            config: Runnable configuration
            coins: List of token identifiers to fetch price charts for

        Returns:
            FetchPriceChartResponse containing price chart data or error
        """
        # Check rate limiting
        context = self.get_context()
        is_rate_limited, error_msg = await self.check_rate_limit(context)
        if is_rate_limited:
            raise ToolException(error_msg)

        # Fetch price chart data from API
        result = await fetch_price_chart(coins=coins)

        # Return the response matching the API structure
        return FetchPriceChartResponse(coins=result["coins"])
