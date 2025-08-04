"""Tool for fetching pool data via DeFi Llama API."""

from typing import Optional

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_pools
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_POOLS_PROMPT = """
This tool fetches comprehensive data about yield-generating pools from DeFi Llama.
Returns data including:
- Pool details (chain, project, symbol)
- TVL and APY information
- Statistical metrics (mean, standard deviation)
- Risk assessments and predictions
- Historical performance data
"""


class PredictionData(BaseModel):
    """Model representing prediction data for a pool."""

    predictedClass: Optional[str] = Field(
        None, description="Predicted direction of APY movement"
    )
    predictedProbability: Optional[float] = Field(
        None, description="Probability of the prediction"
    )
    binnedConfidence: Optional[int] = Field(None, description="Confidence level bucket")


class PoolData(BaseModel):
    """Model representing a single pool's data."""

    chain: str = Field(..., description="Blockchain network")
    project: str = Field(..., description="Protocol or project name")
    symbol: str = Field(..., description="Token or pool symbol")
    tvlUsd: float = Field(..., description="Total Value Locked in USD")
    apyBase: Optional[float] = Field(None, description="Base APY without rewards")
    apyReward: Optional[float] = Field(None, description="Additional APY from rewards")
    apy: Optional[float] = Field(None, description="Total APY including rewards")
    rewardTokens: Optional[list[str]] = Field(
        None, description="List of reward token addresses"
    )
    pool: Optional[str] = Field(None, description="Pool identifier")
    apyPct1D: Optional[float] = Field(None, description="1-day APY percentage change")
    apyPct7D: Optional[float] = Field(None, description="7-day APY percentage change")
    apyPct30D: Optional[float] = Field(None, description="30-day APY percentage change")
    stablecoin: bool = Field(False, description="Whether pool involves stablecoins")
    ilRisk: str = Field("no", description="Impermanent loss risk assessment")
    exposure: str = Field("single", description="Asset exposure type")
    predictions: Optional[PredictionData] = Field(
        None, description="APY movement predictions"
    )
    poolMeta: Optional[str] = Field(None, description="Additional pool metadata")
    mu: Optional[float] = Field(None, description="Mean APY value")
    sigma: Optional[float] = Field(None, description="APY standard deviation")
    count: Optional[int] = Field(None, description="Number of data points")
    outlier: bool = Field(False, description="Whether pool is an outlier")
    underlyingTokens: Optional[list[str]] = Field(
        None, description="List of underlying token addresses"
    )
    il7d: Optional[float] = Field(None, description="7-day impermanent loss")
    apyBase7d: Optional[float] = Field(None, description="7-day base APY")
    apyMean30d: Optional[float] = Field(None, description="30-day mean APY")
    volumeUsd1d: Optional[float] = Field(None, description="24h volume in USD")
    volumeUsd7d: Optional[float] = Field(None, description="7-day volume in USD")
    apyBaseInception: Optional[float] = Field(
        None, description="Base APY since inception"
    )


class FetchPoolsResponse(BaseModel):
    """Response schema for pool data."""

    status: str = Field("success", description="Response status")
    data: list[PoolData] = Field(default_factory=list, description="List of pool data")
    error: Optional[str] = Field(None, description="Error message if any")


class DefiLlamaFetchPools(DefiLlamaBaseTool):
    """Tool for fetching pool data from DeFi Llama.

    This tool retrieves comprehensive data about yield-generating pools,
    including TVL, APYs, risk metrics, and predictions.

    Example:
        pools_tool = DefiLlamaFetchPools(
            skill_store=store,
            agent_id="agent_123",
            agent_store=agent_store
        )
        result = await pools_tool._arun()
    """

    name: str = "defillama_fetch_pools"
    description: str = FETCH_POOLS_PROMPT
    args_schema: None = None  # No input parameters needed

    async def _arun(self, **kwargs) -> FetchPoolsResponse:
        """Fetch pool data.

        Returns:
            FetchPoolsResponse containing pool data or error
        """
        try:
            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return FetchPoolsResponse(error=error_msg)

            # Fetch pool data from API
            result = await fetch_pools()

            # Check for API errors
            if isinstance(result, dict) and "error" in result:
                return FetchPoolsResponse(error=result["error"])

            # Return the response matching the API structure
            return FetchPoolsResponse(**result)

        except Exception as e:
            return FetchPoolsResponse(error=str(e))
