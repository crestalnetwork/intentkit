"""Tool for fetching DEX protocol summary data via DeFi Llama API."""

from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_dex_summary
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_DEX_SUMMARY_PROMPT = (
    """Fetch summary data for a specific DEX protocol via DefiLlama."""
)


class FetchDexSummaryInput(BaseModel):
    """Input schema for fetching DEX protocol summary."""

    protocol: str = Field(..., description="Protocol slug (e.g. 'uniswap')")


class FetchDexSummaryResponse(BaseModel):
    """Response schema for DEX protocol summary data."""

    id: str = Field(..., description="ID")
    name: str = Field(..., description="Name")
    url: str | None = Field(None, description="Website")
    description: str | None = Field(None, description="Description")
    logo: str | None = Field(None, description="Logo URL")
    gecko_id: str | None = Field(None, description="CoinGecko ID")
    cmcId: str | None = Field(None, description="CMC ID")
    chains: list[str] = Field(default_factory=list, description="Chains")
    twitter: str | None = Field(None, description="Twitter")
    treasury: str | None = Field(None, description="Treasury")
    governanceID: list[str] | None = Field(None, description="Governance IDs")
    github: list[str] | None = Field(None, description="GitHub orgs")
    childProtocols: list[str] | None = Field(None, description="Child protocols")
    linkedProtocols: list[str] | None = Field(None, description="Linked protocols")
    disabled: bool | None = Field(None, description="Disabled")
    displayName: str = Field(..., description="Display name")
    module: str | None = Field(None, description="Module")
    category: str | None = Field(None, description="Category")
    methodologyURL: str | None = Field(None, description="Methodology URL")
    methodology: dict[str, Any] | None = Field(None, description="Methodology")
    forkedFrom: list[str] | None = Field(None, description="Forked from")
    audits: str | None = Field(None, description="Audits")
    address: str | None = Field(None, description="Address")
    audit_links: list[str] | None = Field(None, description="Audit links")
    versionKey: str | None = Field(None, description="Version key")
    parentProtocol: str | None = Field(None, description="Parent protocol")
    previousNames: list[str] | None = Field(None, description="Previous names")
    latestFetchIsOk: bool = Field(..., description="Fetch OK")
    slug: str = Field(..., description="Slug")
    protocolType: str = Field(..., description="Type")
    total24h: float | None = Field(None, description="24h volume")
    total48hto24h: float | None = Field(None, description="48h-24h volume")
    total7d: float | None = Field(None, description="7d volume")
    totalAllTime: float | None = Field(None, description="All-time volume")
    totalDataChart: list[Any] = Field(default_factory=list, description="Chart data")
    totalDataChartBreakdown: list[Any] = Field(
        default_factory=list, description="Chart breakdown"
    )
    change_1d: float | None = Field(None, description="1d change %")
    error: str | None = Field(None, description="Error message")


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
    args_schema: ArgsSchema | None = FetchDexSummaryInput

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
