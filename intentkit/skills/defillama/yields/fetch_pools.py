"""Tool for fetching pool data via DeFi Llama API."""

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.base import NoArgsSchema
from intentkit.skills.defillama.api import fetch_pools
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_POOLS_PROMPT = (
    """Fetch all yield pools from DefiLlama with TVL, APY, and risk data."""
)


class PredictionData(BaseModel):
    """Model representing prediction data for a pool."""

    predictedClass: str | None = Field(None, description="APY direction prediction")
    predictedProbability: float | None = Field(
        None, description="Prediction probability"
    )
    binnedConfidence: int | None = Field(None, description="Confidence bucket")


class PoolData(BaseModel):
    """Model representing a single pool's data."""

    chain: str = Field(..., description="Chain")
    project: str = Field(..., description="Project")
    symbol: str = Field(..., description="Symbol")
    tvlUsd: float = Field(..., description="TVL in USD")
    apyBase: float | None = Field(None, description="Base APY")
    apyReward: float | None = Field(None, description="Reward APY")
    apy: float | None = Field(None, description="Total APY")
    rewardTokens: list[str] | None = Field(None, description="Reward tokens")
    pool: str | None = Field(None, description="Pool ID")
    apyPct1D: float | None = Field(None, description="1d APY change %")
    apyPct7D: float | None = Field(None, description="7d APY change %")
    apyPct30D: float | None = Field(None, description="30d APY change %")
    stablecoin: bool = Field(False, description="Stablecoin pool")
    ilRisk: str = Field("no", description="IL risk")
    exposure: str = Field("single", description="Exposure type")
    predictions: PredictionData | None = Field(None, description="APY predictions")
    poolMeta: str | None = Field(None, description="Pool metadata")
    mu: float | None = Field(None, description="Mean APY")
    sigma: float | None = Field(None, description="APY std dev")
    count: int | None = Field(None, description="Data points")
    outlier: bool = Field(False, description="Outlier")
    underlyingTokens: list[str] | None = Field(None, description="Underlying tokens")
    il7d: float | None = Field(None, description="7d IL")
    apyBase7d: float | None = Field(None, description="7d base APY")
    apyMean30d: float | None = Field(None, description="30d mean APY")
    volumeUsd1d: float | None = Field(None, description="24h volume USD")
    volumeUsd7d: float | None = Field(None, description="7d volume USD")
    apyBaseInception: float | None = Field(None, description="Inception base APY")


class FetchPoolsResponse(BaseModel):
    """Response schema for pool data."""

    status: str = Field("success", description="Status")
    data: list[PoolData] = Field(default_factory=list, description="Pools")
    error: str | None = Field(default=None, description="Error message")


class DefiLlamaFetchPools(DefiLlamaBaseTool):
    """Tool for fetching pool data from DeFi Llama.

    This tool retrieves comprehensive data about yield-generating pools,
    including TVL, APYs, risk metrics, and predictions.

    Example:
        pools_tool = DefiLlamaFetchPools(
            ,
            agent_id="agent_123",
            agent=agent
        )
        result = await pools_tool._arun()
    """

    name: str = "defillama_fetch_pools"
    description: str = FETCH_POOLS_PROMPT
    args_schema: ArgsSchema | None = NoArgsSchema  # No input parameters needed

    async def _arun(self, **kwargs) -> FetchPoolsResponse:
        """Fetch pool data.

        Returns:
            FetchPoolsResponse containing pool data or error
        """
        # Check rate limiting
        context = self.get_context()
        is_rate_limited, error_msg = await self.check_rate_limit(context)
        if is_rate_limited:
            raise ToolException(error_msg)

        # Fetch pool data from API
        result = await fetch_pools()

        # Return the response matching the API structure
        return FetchPoolsResponse(**result)
