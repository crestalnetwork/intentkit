"""Tool for fetching total historical TVL via DeFiLlama API."""

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_historical_tvl
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_TOTAL_HISTORICAL_TVL_PROMPT = (
    """Fetch historical aggregate TVL across all chains via DefiLlama."""
)


class HistoricalTVLDataPoint(BaseModel):
    """Model representing a single TVL data point."""

    date: int = Field(..., description="Unix timestamp")
    tvl: float = Field(..., description="TVL in USD")


class FetchHistoricalTVLInput(BaseModel):
    """Input schema for fetching historical TVL data.

    This endpoint doesn't require any parameters as it returns
    global TVL data across all chains.
    """

    pass


class FetchHistoricalTVLResponse(BaseModel):
    """Response schema for historical TVL data."""

    data: list[HistoricalTVLDataPoint] = Field(
        default_factory=list, description="TVL data points"
    )
    error: str | None = Field(default=None, description="Error message")


class DefiLlamaFetchHistoricalTvl(DefiLlamaBaseTool):
    """Tool for fetching historical TVL data across all blockchains.

    This tool fetches the complete Total Value Locked (TVL) history aggregated
    across all chains using the DeFiLlama API. It includes rate limiting to
    ensure reliable data retrieval.

    Example:
        tvl_tool = DefiLlamaFetchHistoricalTvl(
            ,
            agent_id="agent_123",
            agent=agent
        )
        result = await tvl_tool._arun()
    """

    name: str = "defillama_fetch_total_historical_tvl"
    description: str = FETCH_TOTAL_HISTORICAL_TVL_PROMPT
    args_schema: ArgsSchema | None = FetchHistoricalTVLInput

    async def _arun(self, **kwargs) -> FetchHistoricalTVLResponse:
        """Fetch historical TVL data across all chains.

        Returns:
            FetchHistoricalTVLResponse containing TVL history or error
        """
        # Check rate limiting
        context = self.get_context()
        is_rate_limited, error_msg = await self.check_rate_limit(context)
        if is_rate_limited:
            raise ToolException(error_msg)

        # Fetch TVL history from API
        result = await fetch_historical_tvl()

        # Parse response into our schema
        data_points = [HistoricalTVLDataPoint(**point) for point in result]

        return FetchHistoricalTVLResponse(data=data_points)
