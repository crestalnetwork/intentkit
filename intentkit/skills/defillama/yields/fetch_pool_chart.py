"""Tool for fetching pool chart data via DeFi Llama API."""

from typing import List, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_pool_chart
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_POOL_CHART_PROMPT = """
This tool fetches historical chart data from DeFi Llama for a specific pool.
Required:
- Pool ID
Returns historical data including:
- TVL in USD
- APY metrics (base, reward, total)
- Timestamps for each data point
"""


class PoolDataPoint(BaseModel):
    """Model representing a single historical data point."""

    timestamp: str = Field(..., description="ISO formatted timestamp of the data point")
    tvlUsd: float = Field(..., description="Total Value Locked in USD")
    apy: Optional[float] = Field(None, description="Total APY including rewards")
    apyBase: Optional[float] = Field(None, description="Base APY without rewards")
    apyReward: Optional[float] = Field(None, description="Additional APY from rewards")
    il7d: Optional[float] = Field(None, description="7-day impermanent loss")
    apyBase7d: Optional[float] = Field(None, description="7-day base APY")


class FetchPoolChartInput(BaseModel):
    """Input schema for fetching pool chart data."""

    pool_id: str = Field(..., description="ID of the pool to fetch chart data for")


class FetchPoolChartResponse(BaseModel):
    """Response schema for pool chart data."""

    status: str = Field("success", description="Response status")
    data: List[PoolDataPoint] = Field(
        default_factory=list, description="List of historical data points"
    )
    error: Optional[str] = Field(None, description="Error message if any")


class DefiLlamaFetchPoolChart(DefiLlamaBaseTool):
    """Tool for fetching pool chart data from DeFi Llama.

    This tool retrieves historical data for a specific pool, including
    TVL and APY metrics over time.

    Example:
        chart_tool = DefiLlamaFetchPoolChart(
            skill_store=store,
            agent_id="agent_123",
            agent_store=agent_store
        )
        result = await chart_tool._arun(
            pool_id="747c1d2a-c668-4682-b9f9-296708a3dd90"
        )
    """

    name: str = "defillama_fetch_pool_chart"
    description: str = FETCH_POOL_CHART_PROMPT
    args_schema: Type[BaseModel] = FetchPoolChartInput

    async def _arun(self, pool_id: str) -> FetchPoolChartResponse:
        """Fetch historical chart data for the given pool.

        Args:
            pool_id: ID of the pool to fetch chart data for

        Returns:
            FetchPoolChartResponse containing historical data or error
        """
        try:
            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return FetchPoolChartResponse(error=error_msg)

            # Fetch chart data from API
            result = await fetch_pool_chart(pool_id=pool_id)

            # Check for API errors
            if isinstance(result, dict) and "error" in result:
                return FetchPoolChartResponse(error=result["error"])

            # Return the response matching the API structure
            return FetchPoolChartResponse(**result)

        except Exception as e:
            return FetchPoolChartResponse(error=str(e))
