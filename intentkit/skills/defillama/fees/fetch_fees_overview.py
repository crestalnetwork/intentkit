"""Tool for fetching fees overview data via DeFi Llama API."""

from typing import Dict, List, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_fees_overview
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_FEES_OVERVIEW_PROMPT = """
This tool fetches comprehensive overview data for protocol fees from DeFi Llama.
Returns detailed metrics including:
- Total fees across different timeframes
- Change percentages
- Protocol-specific data
- Chain breakdowns
"""


class ProtocolMethodology(BaseModel):
    """Model representing protocol methodology data."""

    UserFees: Optional[str] = Field(None, description="Description of user fees")
    Fees: Optional[str] = Field(None, description="Description of fees")
    Revenue: Optional[str] = Field(None, description="Description of revenue")
    ProtocolRevenue: Optional[str] = Field(
        None, description="Description of protocol revenue"
    )
    HoldersRevenue: Optional[str] = Field(
        None, description="Description of holders revenue"
    )
    SupplySideRevenue: Optional[str] = Field(
        None, description="Description of supply side revenue"
    )


class Protocol(BaseModel):
    """Model representing protocol data."""

    name: str = Field(..., description="Protocol name")
    displayName: str = Field(..., description="Display name of protocol")
    category: str = Field(..., description="Protocol category")
    logo: str = Field(..., description="Logo URL")
    chains: List[str] = Field(..., description="Supported chains")
    module: str = Field(..., description="Protocol module")
    total24h: Optional[float] = Field(None, description="24-hour total fees")
    total7d: Optional[float] = Field(None, description="7-day total fees")
    total30d: Optional[float] = Field(None, description="30-day total fees")
    total1y: Optional[float] = Field(None, description="1-year total fees")
    totalAllTime: Optional[float] = Field(None, description="All-time total fees")
    change_1d: Optional[float] = Field(None, description="24-hour change percentage")
    change_7d: Optional[float] = Field(None, description="7-day change percentage")
    change_1m: Optional[float] = Field(None, description="30-day change percentage")
    methodology: Optional[ProtocolMethodology] = Field(
        None, description="Protocol methodology"
    )
    breakdown24h: Optional[Dict[str, Dict[str, float]]] = Field(
        None, description="24-hour breakdown by chain"
    )
    breakdown30d: Optional[Dict[str, Dict[str, float]]] = Field(
        None, description="30-day breakdown by chain"
    )


class FetchFeesOverviewResponse(BaseModel):
    """Response schema for fees overview data."""

    total24h: float = Field(..., description="Total fees in last 24 hours")
    total7d: float = Field(..., description="Total fees in last 7 days")
    total30d: float = Field(..., description="Total fees in last 30 days")
    total1y: float = Field(..., description="Total fees in last year")
    change_1d: float = Field(..., description="24-hour change percentage")
    change_7d: float = Field(..., description="7-day change percentage")
    change_1m: float = Field(..., description="30-day change percentage")
    allChains: List[str] = Field(..., description="List of all chains")
    protocols: List[Protocol] = Field(..., description="List of protocols")
    error: Optional[str] = Field(None, description="Error message if any")


class DefiLlamaFetchFeesOverview(DefiLlamaBaseTool):
    """Tool for fetching fees overview data from DeFi Llama.

    This tool retrieves comprehensive data about protocol fees,
    including fee metrics, change percentages, and detailed protocol information.

    Example:
        overview_tool = DefiLlamaFetchFeesOverview(
            skill_store=store,
            agent_id="agent_123",
            agent_store=agent_store
        )
        result = await overview_tool._arun()
    """

    name: str = "defillama_fetch_fees_overview"
    description: str = FETCH_FEES_OVERVIEW_PROMPT

    class EmptyArgsSchema(BaseModel):
        """Empty schema for no input parameters."""

        pass

    args_schema: Type[BaseModel] = EmptyArgsSchema

    async def _arun(self, **kwargs) -> FetchFeesOverviewResponse:
        """Fetch overview data for protocol fees.

        Returns:
            FetchFeesOverviewResponse containing comprehensive fee data or error
        """
        try:
            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return FetchFeesOverviewResponse(error=error_msg)

            # Fetch fees data from API
            result = await fetch_fees_overview()

            # Check for API errors
            if isinstance(result, dict) and "error" in result:
                return FetchFeesOverviewResponse(error=result["error"])

            # Return the parsed response
            return FetchFeesOverviewResponse(**result)

        except Exception as e:
            return FetchFeesOverviewResponse(error=str(e))
