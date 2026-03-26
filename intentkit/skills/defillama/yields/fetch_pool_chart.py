"""Tool for fetching pool chart data via DeFi Llama API."""

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_pool_chart
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_POOL_CHART_PROMPT = (
    """Fetch historical TVL and APY chart data for a yield pool via DefiLlama."""
)


class PoolDataPoint(BaseModel):
    """Model representing a single historical data point."""

    timestamp: str = Field(..., description="ISO timestamp")
    tvlUsd: float = Field(..., description="TVL in USD")
    apy: float | None = Field(None, description="Total APY")
    apyBase: float | None = Field(None, description="Base APY")
    apyReward: float | None = Field(None, description="Reward APY")
    il7d: float | None = Field(None, description="7d IL")
    apyBase7d: float | None = Field(None, description="7d base APY")


class FetchPoolChartInput(BaseModel):
    """Input schema for fetching pool chart data."""

    pool_id: str = Field(..., description="Pool ID")


class FetchPoolChartResponse(BaseModel):
    """Response schema for pool chart data."""

    status: str = Field("success", description="Status")
    data: list[PoolDataPoint] = Field(default_factory=list, description="Data points")
    error: str | None = Field(None, description="Error message")


class DefiLlamaFetchPoolChart(DefiLlamaBaseTool):
    """Tool for fetching pool chart data from DeFi Llama.

    This tool retrieves historical data for a specific pool, including
    TVL and APY metrics over time.

    Example:
        chart_tool = DefiLlamaFetchPoolChart(
            ,
            agent_id="agent_123",
            agent=agent
        )
        result = await chart_tool._arun(
            pool_id="747c1d2a-c668-4682-b9f9-296708a3dd90"
        )
    """

    name: str = "defillama_fetch_pool_chart"
    description: str = FETCH_POOL_CHART_PROMPT
    args_schema: ArgsSchema | None = FetchPoolChartInput

    async def _arun(self, pool_id: str) -> FetchPoolChartResponse:
        """Fetch historical chart data for the given pool.

        Args:
            pool_id: ID of the pool to fetch chart data for

        Returns:
            FetchPoolChartResponse containing historical data or error
        """
        # Check rate limiting
        context = self.get_context()
        is_rate_limited, error_msg = await self.check_rate_limit(context)
        if is_rate_limited:
            raise ToolException(error_msg)

        # Fetch chart data from API
        result = await fetch_pool_chart(pool_id=pool_id)

        # Return the response matching the API structure
        return FetchPoolChartResponse(**result)
