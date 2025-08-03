"""Tool for fetching total historical TVL via DeFiLlama API."""

from typing import List, Type

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_historical_tvl
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_TOTAL_HISTORICAL_TVL_PROMPT = """
This tool fetches historical Total Value Locked (TVL) data across all blockchains.
Returns a time series of aggregate TVL values with their corresponding dates.
No input parameters are required as this endpoint returns global DeFi TVL data.
"""


class HistoricalTVLDataPoint(BaseModel):
    """Model representing a single TVL data point."""

    date: int = Field(..., description="Unix timestamp of the TVL measurement")
    tvl: float = Field(..., description="Total Value Locked in USD at this timestamp")


class FetchHistoricalTVLInput(BaseModel):
    """Input schema for fetching historical TVL data.

    This endpoint doesn't require any parameters as it returns
    global TVL data across all chains.
    """

    pass


class FetchHistoricalTVLResponse(BaseModel):
    """Response schema for historical TVL data."""

    data: List[HistoricalTVLDataPoint] = Field(
        default_factory=list,
        description="List of historical TVL data points across all chains",
    )
    error: str | None = Field(default=None, description="Error message if any")


class DefiLlamaFetchHistoricalTvl(DefiLlamaBaseTool):
    """Tool for fetching historical TVL data across all blockchains.

    This tool fetches the complete Total Value Locked (TVL) history aggregated
    across all chains using the DeFiLlama API. It includes rate limiting to
    ensure reliable data retrieval.

    Example:
        tvl_tool = DefiLlamaFetchHistoricalTvl(
            skill_store=store,
            agent_id="agent_123",
            agent_store=agent_store
        )
        result = await tvl_tool._arun()
    """

    name: str = "defillama_fetch_total_historical_tvl"
    description: str = FETCH_TOTAL_HISTORICAL_TVL_PROMPT
    args_schema: Type[BaseModel] = FetchHistoricalTVLInput

    async def _arun(self, **kwargs) -> FetchHistoricalTVLResponse:
        """Fetch historical TVL data across all chains.

        Returns:
            FetchHistoricalTVLResponse containing TVL history or error
        """
        try:
            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return FetchHistoricalTVLResponse(error=error_msg)

            # Fetch TVL history from API
            result = await fetch_historical_tvl()

            # Check for API errors
            if isinstance(result, dict) and "error" in result:
                return FetchHistoricalTVLResponse(error=result["error"])

            # Parse response into our schema
            data_points = [HistoricalTVLDataPoint(**point) for point in result]

            return FetchHistoricalTVLResponse(data=data_points)

        except Exception as e:
            return FetchHistoricalTVLResponse(error=str(e))
