"""Tool for fetching stablecoin charts via DeFi Llama API."""

from typing import List, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_stablecoin_charts
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_STABLECOIN_CHARTS_PROMPT = """
This tool fetches historical circulating supply data from DeFi Llama for a specific stablecoin.
Required:
- Stablecoin ID
Optional:
- Chain name for chain-specific data
Returns historical data including:
- Total circulating supply
- Circulating supply in USD
- Daily data points
"""


class CirculatingSupply(BaseModel):
    """Model representing circulating supply amounts."""

    peggedUSD: float = Field(..., description="Amount pegged to USD")


class StablecoinDataPoint(BaseModel):
    """Model representing a single historical data point."""

    date: str = Field(..., description="Unix timestamp of the data point")
    totalCirculating: CirculatingSupply = Field(
        ..., description="Total circulating supply"
    )
    totalCirculatingUSD: CirculatingSupply = Field(
        ..., description="Total circulating supply in USD"
    )


class FetchStablecoinChartsInput(BaseModel):
    """Input schema for fetching stablecoin chart data."""

    stablecoin_id: str = Field(
        ..., description="ID of the stablecoin to fetch data for"
    )
    chain: Optional[str] = Field(
        None, description="Optional chain name for chain-specific data"
    )


class FetchStablecoinChartsResponse(BaseModel):
    """Response schema for stablecoin chart data."""

    data: List[StablecoinDataPoint] = Field(
        default_factory=list, description="List of historical data points"
    )
    chain: Optional[str] = Field(
        None, description="Chain name if chain-specific data was requested"
    )
    error: Optional[str] = Field(None, description="Error message if any")


class DefiLlamaFetchStablecoinCharts(DefiLlamaBaseTool):
    """Tool for fetching stablecoin chart data from DeFi Llama.

    This tool retrieves historical circulating supply data for a specific stablecoin,
    optionally filtered by chain.

    Example:
        charts_tool = DefiLlamaFetchStablecoinCharts(
            skill_store=store,
            agent_id="agent_123",
            agent_store=agent_store
        )
        # Get all chains data
        result = await charts_tool._arun(stablecoin_id="1")
        # Get chain-specific data
        result = await charts_tool._arun(stablecoin_id="1", chain="ethereum")
    """

    name: str = "defillama_fetch_stablecoin_charts"
    description: str = FETCH_STABLECOIN_CHARTS_PROMPT
    args_schema: Type[BaseModel] = FetchStablecoinChartsInput

    async def _arun(
        self, stablecoin_id: str, chain: Optional[str] = None
    ) -> FetchStablecoinChartsResponse:
        """Fetch historical chart data for the given stablecoin.

        Args:
            config: Runnable configuration
            stablecoin_id: ID of the stablecoin to fetch data for
            chain: Optional chain name for chain-specific data

        Returns:
            FetchStablecoinChartsResponse containing historical data or error
        """
        try:
            # Validate chain if provided
            if chain:
                is_valid, normalized_chain = await self.validate_chain(chain)
                if not is_valid:
                    return FetchStablecoinChartsResponse(
                        error=f"Invalid chain: {chain}"
                    )
                chain = normalized_chain

            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return FetchStablecoinChartsResponse(error=error_msg)

            # Fetch chart data from API
            result = await fetch_stablecoin_charts(
                stablecoin_id=stablecoin_id, chain=chain
            )

            # Check for API errors
            if isinstance(result, dict) and "error" in result:
                return FetchStablecoinChartsResponse(error=result["error"])

            # Parse response data
            return FetchStablecoinChartsResponse(data=result, chain=chain)

        except Exception as e:
            return FetchStablecoinChartsResponse(error=str(e))
