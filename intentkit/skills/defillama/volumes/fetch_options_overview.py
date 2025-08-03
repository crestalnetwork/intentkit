"""Tool for fetching options overview data via DeFi Llama API."""

from typing import Dict, List, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_options_overview
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_OPTIONS_OVERVIEW_PROMPT = """
This tool fetches comprehensive overview data for all options protocols from DeFi Llama.
Returns detailed metrics including:
- Total volumes across different timeframes
- Change percentages
- Protocol-specific data
- Chain breakdowns
"""


class ProtocolMethodology(BaseModel):
    """Model representing protocol methodology data."""

    UserFees: Optional[str] = Field(None, description="User fees description")
    Fees: Optional[str] = Field(None, description="Fees description")
    Revenue: Optional[str] = Field(None, description="Revenue description")
    ProtocolRevenue: Optional[str] = Field(
        None, description="Protocol revenue description"
    )
    HoldersRevenue: Optional[str] = Field(
        None, description="Holders revenue description"
    )
    SupplySideRevenue: Optional[str] = Field(
        None, description="Supply side revenue description"
    )


class Protocol(BaseModel):
    """Model representing protocol data."""

    name: str = Field(..., description="Protocol name")
    displayName: str = Field(..., description="Display name of protocol")
    defillamaId: str = Field(..., description="DeFi Llama ID")
    category: str = Field(..., description="Protocol category")
    logo: str = Field(..., description="Logo URL")
    chains: List[str] = Field(..., description="Supported chains")
    module: str = Field(..., description="Protocol module")
    total24h: Optional[float] = Field(None, description="24-hour total")
    total7d: Optional[float] = Field(None, description="7-day total")
    total30d: Optional[float] = Field(None, description="30-day total")
    total1y: Optional[float] = Field(None, description="1-year total")
    totalAllTime: Optional[float] = Field(None, description="All-time total")
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


class FetchOptionsOverviewResponse(BaseModel):
    """Response schema for options overview data."""

    total24h: float = Field(..., description="Total volume in last 24 hours")
    total7d: float = Field(..., description="Total volume in last 7 days")
    total30d: float = Field(..., description="Total volume in last 30 days")
    total1y: float = Field(..., description="Total volume in last year")
    change_1d: float = Field(..., description="24-hour change percentage")
    change_7d: float = Field(..., description="7-day change percentage")
    change_1m: float = Field(..., description="30-day change percentage")
    allChains: List[str] = Field(..., description="List of all chains")
    protocols: List[Protocol] = Field(..., description="List of protocols")
    error: Optional[str] = Field(None, description="Error message if any")


class DefiLlamaFetchOptionsOverview(DefiLlamaBaseTool):
    """Tool for fetching options overview data from DeFi Llama.

    This tool retrieves comprehensive data about all options protocols,
    including volume metrics, change percentages, and detailed protocol information.

    Example:
        overview_tool = DefiLlamaFetchOptionsOverview(
            skill_store=store,
            agent_id="agent_123",
            agent_store=agent_store
        )
        result = await overview_tool._arun()
    """

    name: str = "defillama_fetch_options_overview"
    description: str = FETCH_OPTIONS_OVERVIEW_PROMPT

    class EmptyArgsSchema(BaseModel):
        """Empty schema for no input parameters."""

        pass

    args_schema: Type[BaseModel] = EmptyArgsSchema

    async def _arun(self, **kwargs) -> FetchOptionsOverviewResponse:
        """Fetch overview data for all options protocols.

        Returns:
            FetchOptionsOverviewResponse containing comprehensive overview data or error
        """
        try:
            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return FetchOptionsOverviewResponse(error=error_msg)

            # Fetch overview data from API
            result = await fetch_options_overview()

            # Check for API errors
            if isinstance(result, dict) and "error" in result:
                return FetchOptionsOverviewResponse(error=result["error"])

            # Return the parsed response
            return FetchOptionsOverviewResponse(**result)

        except Exception as e:
            return FetchOptionsOverviewResponse(error=str(e))
