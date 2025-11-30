"""Tool for fetching DEX overview data via DeFi Llama API."""

from typing import Any

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_dex_overview
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_DEX_OVERVIEW_PROMPT = """
This tool fetches comprehensive overview data for DEX protocols from DeFi Llama.
Returns:
- Chain statistics and breakdowns
- Protocol-specific metrics
- Change percentages
- Total volume data
"""


class MethodologyInfo(BaseModel):
    """Model representing methodology information."""

    UserFees: str | None = Field(None, description="User fee information")
    Fees: str | None = Field(None, description="Fee structure")
    Revenue: str | None = Field(None, description="Revenue model")
    ProtocolRevenue: str | None = Field(None, description="Protocol revenue info")
    HoldersRevenue: str | None = Field(None, description="Holder revenue info")
    SupplySideRevenue: str | None = Field(None, description="Supply side revenue info")


class ProtocolInfo(BaseModel):
    """Model representing individual protocol data."""

    total24h: float | None = Field(None, description="24h total")
    total48hto24h: float | None = Field(None, description="48h to 24h total")
    total7d: float | None = Field(None, description="7d total")
    total14dto7d: float | None = Field(None, description="14d to 7d total")
    total60dto30d: float | None = Field(None, description="60d to 30d total")
    total30d: float | None = Field(None, description="30d total")
    total1y: float | None = Field(None, description="1y total")
    totalAllTime: float | None = Field(None, description="All time total")
    average1y: float | None = Field(None, description="1y average")
    change_1d: float | None = Field(None, description="1d change")
    change_7d: float | None = Field(None, description="7d change")
    change_1m: float | None = Field(None, description="1m change")
    change_7dover7d: float | None = Field(None, description="7d over 7d change")
    change_30dover30d: float | None = Field(None, description="30d over 30d change")
    breakdown24h: dict[str, dict[str, float]] | None = Field(
        None, description="24h breakdown by chain"
    )
    breakdown30d: dict[str, dict[str, float]] | None = Field(
        None, description="30d breakdown by chain"
    )
    total7DaysAgo: float | None = Field(None, description="Total 7 days ago")
    total30DaysAgo: float | None = Field(None, description="Total 30 days ago")
    defillamaId: str | None = Field(None, description="DeFi Llama ID")
    name: str = Field(..., description="Protocol name")
    displayName: str = Field(..., description="Display name")
    module: str = Field(..., description="Module name")
    category: str = Field(..., description="Protocol category")
    logo: str | None = Field(None, description="Logo URL")
    chains: list[str] = Field(..., description="Supported chains")
    protocolType: str = Field(..., description="Protocol type")
    methodologyURL: str | None = Field(None, description="Methodology URL")
    methodology: MethodologyInfo | None = Field(None, description="Methodology details")
    latestFetchIsOk: bool = Field(..., description="Latest fetch status")
    disabled: bool | None = Field(None, description="Whether protocol is disabled")
    parentProtocol: str | None = Field(None, description="Parent protocol")
    slug: str = Field(..., description="Protocol slug")
    linkedProtocols: list[str] | None = Field(None, description="Linked protocols")
    id: str = Field(..., description="Protocol ID")


class FetchDexOverviewResponse(BaseModel):
    """Response schema for DEX overview data."""

    totalDataChart: list[Any] = Field(
        default_factory=list, description="Total data chart points"
    )
    totalDataChartBreakdown: list[Any] = Field(
        default_factory=list, description="Total data chart breakdown"
    )
    breakdown24h: dict[str, dict[str, float]] | None = Field(
        None, description="24h breakdown by chain"
    )
    breakdown30d: dict[str, dict[str, float]] | None = Field(
        None, description="30d breakdown by chain"
    )
    chain: str | None = Field(None, description="Specific chain")
    allChains: list[str] = Field(..., description="List of all chains")
    total24h: float = Field(..., description="24h total")
    total48hto24h: float = Field(..., description="48h to 24h total")
    total7d: float = Field(..., description="7d total")
    total14dto7d: float = Field(..., description="14d to 7d total")
    total60dto30d: float = Field(..., description="60d to 30d total")
    total30d: float = Field(..., description="30d total")
    total1y: float = Field(..., description="1y total")
    change_1d: float = Field(..., description="1d change")
    change_7d: float = Field(..., description="7d change")
    change_1m: float = Field(..., description="1m change")
    change_7dover7d: float = Field(..., description="7d over 7d change")
    change_30dover30d: float = Field(..., description="30d over 30d change")
    total7DaysAgo: float = Field(..., description="Total 7 days ago")
    total30DaysAgo: float = Field(..., description="Total 30 days ago")
    protocols: list[ProtocolInfo] = Field(..., description="List of protocol data")
    error: str | None = Field(None, description="Error message if any")


class DefiLlamaFetchDexOverview(DefiLlamaBaseTool):
    """Tool for fetching DEX overview data from DeFi Llama.

    This tool retrieves comprehensive data about DEX protocols, including
    volumes, metrics, and chain breakdowns.

    Example:
        overview_tool = DefiLlamaFetchDexOverview(
            ,
            agent_id="agent_123",
            agent=agent
        )
        result = await overview_tool._arun()
    """

    name: str = "defillama_fetch_dex_overview"
    description: str = FETCH_DEX_OVERVIEW_PROMPT
    args_schema: None = None  # No input parameters needed

    async def _arun(self, **kwargs) -> FetchDexOverviewResponse:
        """Fetch DEX overview data.

        Returns:
            FetchDexOverviewResponse containing overview data or error
        """
        try:
            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return FetchDexOverviewResponse(error=error_msg)

            # Fetch overview data from API
            result = await fetch_dex_overview()

            # Check for API errors
            if isinstance(result, dict) and "error" in result:
                return FetchDexOverviewResponse(error=result["error"])

            # Return the response matching the API structure
            return FetchDexOverviewResponse(**result)

        except Exception as e:
            return FetchDexOverviewResponse(error=str(e))
