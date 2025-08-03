"""Tool for fetching DEX protocol summary data via DeFi Llama API."""

from typing import Dict, List, Optional, Type

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
    url: Optional[str] = Field(None, description="Protocol website URL")
    description: Optional[str] = Field(None, description="Protocol description")
    logo: Optional[str] = Field(None, description="Logo URL")
    gecko_id: Optional[str] = Field(None, description="CoinGecko ID")
    cmcId: Optional[str] = Field(None, description="CoinMarketCap ID")
    chains: List[str] = Field(default_factory=list, description="Supported chains")
    twitter: Optional[str] = Field(None, description="Twitter handle")
    treasury: Optional[str] = Field(None, description="Treasury identifier")
    governanceID: Optional[List[str]] = Field(None, description="Governance IDs")
    github: Optional[List[str]] = Field(None, description="GitHub organizations")
    childProtocols: Optional[List[str]] = Field(None, description="Child protocols")
    linkedProtocols: Optional[List[str]] = Field(None, description="Linked protocols")
    disabled: Optional[bool] = Field(None, description="Whether protocol is disabled")
    displayName: str = Field(..., description="Display name")
    module: Optional[str] = Field(None, description="Module name")
    category: Optional[str] = Field(None, description="Protocol category")
    methodologyURL: Optional[str] = Field(None, description="Methodology URL")
    methodology: Optional[Dict] = Field(None, description="Methodology details")
    forkedFrom: Optional[List[str]] = Field(None, description="Forked from protocols")
    audits: Optional[str] = Field(None, description="Audit information")
    address: Optional[str] = Field(None, description="Contract address")
    audit_links: Optional[List[str]] = Field(None, description="Audit links")
    versionKey: Optional[str] = Field(None, description="Version key")
    parentProtocol: Optional[str] = Field(None, description="Parent protocol")
    previousNames: Optional[List[str]] = Field(None, description="Previous names")
    latestFetchIsOk: bool = Field(..., description="Latest fetch status")
    slug: str = Field(..., description="Protocol slug")
    protocolType: str = Field(..., description="Protocol type")
    total24h: Optional[float] = Field(None, description="24h total volume")
    total48hto24h: Optional[float] = Field(None, description="48h to 24h total volume")
    total7d: Optional[float] = Field(None, description="7d total volume")
    totalAllTime: Optional[float] = Field(None, description="All time total volume")
    totalDataChart: List = Field(default_factory=list, description="Total data chart")
    totalDataChartBreakdown: List = Field(
        default_factory=list, description="Chart breakdown"
    )
    change_1d: Optional[float] = Field(None, description="1d change percentage")
    error: Optional[str] = Field(None, description="Error message if any")


class DefiLlamaFetchDexSummary(DefiLlamaBaseTool):
    """Tool for fetching DEX protocol summary data from DeFi Llama.

    This tool retrieves detailed information about a specific DEX protocol,
    including metadata, metrics, and related protocols.

    Example:
        summary_tool = DefiLlamaFetchDexSummary(
            skill_store=store,
            agent_id="agent_123",
            agent_store=agent_store
        )
        result = await summary_tool._arun(protocol="uniswap")
    """

    name: str = "defillama_fetch_dex_summary"
    description: str = FETCH_DEX_SUMMARY_PROMPT
    args_schema: Type[BaseModel] = FetchDexSummaryInput

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
