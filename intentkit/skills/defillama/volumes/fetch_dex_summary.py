"""Tool for fetching DEX protocol summary data via DeFi Llama API."""

from typing import Any

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_dex_summary
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_DEX_SUMMARY_PROMPT = """
This tool fetches summary data for a specific DEX protocol from DeFi Llama.
Required:
- Protocol identifier
Returns:
- Protocol details and metadata
- Volume metrics
- Social links and identifiers
- Child protocols and versions
"""


class FetchDexSummaryInput(BaseModel):
    """Input schema for fetching DEX protocol summary."""

    protocol: str = Field(..., description="Protocol identifier (e.g. 'uniswap')")


class FetchDexSummaryResponse(BaseModel):
    """Response schema for DEX protocol summary data."""

    id: str = Field(..., description="Protocol ID")
    name: str = Field(..., description="Protocol name")
    url: str | None = Field(None, description="Protocol website URL")
    description: str | None = Field(None, description="Protocol description")
    logo: str | None = Field(None, description="Logo URL")
    gecko_id: str | None = Field(None, description="CoinGecko ID")
    cmcId: str | None = Field(None, description="CoinMarketCap ID")
    chains: list[str] = Field(default_factory=list, description="Supported chains")
    twitter: str | None = Field(None, description="Twitter handle")
    treasury: str | None = Field(None, description="Treasury identifier")
    governanceID: list[str] | None = Field(None, description="Governance IDs")
    github: list[str] | None = Field(None, description="GitHub organizations")
    childProtocols: list[str] | None = Field(None, description="Child protocols")
    linkedProtocols: list[str] | None = Field(None, description="Linked protocols")
    disabled: bool | None = Field(None, description="Whether protocol is disabled")
    displayName: str = Field(..., description="Display name")
    module: str | None = Field(None, description="Module name")
    category: str | None = Field(None, description="Protocol category")
    methodologyURL: str | None = Field(None, description="Methodology URL")
    methodology: dict[str, Any] | None = Field(None, description="Methodology details")
    forkedFrom: list[str] | None = Field(None, description="Forked from protocols")
    audits: str | None = Field(None, description="Audit information")
    address: str | None = Field(None, description="Contract address")
    audit_links: list[str] | None = Field(None, description="Audit links")
    versionKey: str | None = Field(None, description="Version key")
    parentProtocol: str | None = Field(None, description="Parent protocol")
    previousNames: list[str] | None = Field(None, description="Previous names")
    latestFetchIsOk: bool = Field(..., description="Latest fetch status")
    slug: str = Field(..., description="Protocol slug")
    protocolType: str = Field(..., description="Protocol type")
    total24h: float | None = Field(None, description="24h total volume")
    total48hto24h: float | None = Field(None, description="48h to 24h total volume")
    total7d: float | None = Field(None, description="7d total volume")
    totalAllTime: float | None = Field(None, description="All time total volume")
    totalDataChart: list[Any] = Field(
        default_factory=list, description="Total data chart"
    )
    totalDataChartBreakdown: list[Any] = Field(
        default_factory=list, description="Chart breakdown"
    )
    change_1d: float | None = Field(None, description="1d change percentage")
    error: str | None = Field(None, description="Error message if any")


class DefiLlamaFetchDexSummary(DefiLlamaBaseTool):
    """Tool for fetching DEX protocol summary data from DeFi Llama.

    This tool retrieves detailed information about a specific DEX protocol,
    including metadata, metrics, and related protocols.

    Example:
        summary_tool = DefiLlamaFetchDexSummary(
            ,
            agent_id="agent_123",
            agent=agent
        )
        result = await summary_tool._arun(protocol="uniswap")
    """

    name: str = "defillama_fetch_dex_summary"
    description: str = FETCH_DEX_SUMMARY_PROMPT
    args_schema: type[BaseModel] = FetchDexSummaryInput

    async def _arun(self, protocol: str) -> FetchDexSummaryResponse:
        """Fetch summary data for the given DEX protocol.

        Args:
            config: Runnable configuration
            protocol: Protocol identifier

        Returns:
            FetchDexSummaryResponse containing protocol data or error
        """
        try:
            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return FetchDexSummaryResponse(error=error_msg)

            # Fetch protocol data from API
            result = await fetch_dex_summary(protocol=protocol)

            # Check for API errors
            if isinstance(result, dict) and "error" in result:
                return FetchDexSummaryResponse(error=result["error"])

            # Return the response matching the API structure
            return FetchDexSummaryResponse(**result)

        except Exception as e:
            return FetchDexSummaryResponse(error=str(e))
