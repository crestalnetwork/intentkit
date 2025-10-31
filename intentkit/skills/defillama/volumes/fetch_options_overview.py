"""Tool for fetching options overview data via DeFi Llama API."""

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

    UserFees: str | None = Field(None, description="User fees description")
    Fees: str | None = Field(None, description="Fees description")
    Revenue: str | None = Field(None, description="Revenue description")
    ProtocolRevenue: str | None = Field(
        None, description="Protocol revenue description"
    )
    HoldersRevenue: str | None = Field(None, description="Holders revenue description")
    SupplySideRevenue: str | None = Field(
        None, description="Supply side revenue description"
    )


class Protocol(BaseModel):
    """Model representing protocol data."""

    name: str = Field(..., description="Protocol name")
    displayName: str = Field(..., description="Display name of protocol")
    defillamaId: str = Field(..., description="DeFi Llama ID")
    category: str = Field(..., description="Protocol category")
    logo: str = Field(..., description="Logo URL")
    chains: list[str] = Field(..., description="Supported chains")
    module: str = Field(..., description="Protocol module")
    total24h: float | None = Field(None, description="24-hour total")
    total7d: float | None = Field(None, description="7-day total")
    total30d: float | None = Field(None, description="30-day total")
    total1y: float | None = Field(None, description="1-year total")
    totalAllTime: float | None = Field(None, description="All-time total")
    change_1d: float | None = Field(None, description="24-hour change percentage")
    change_7d: float | None = Field(None, description="7-day change percentage")
    change_1m: float | None = Field(None, description="30-day change percentage")
    methodology: ProtocolMethodology | None = Field(
        None, description="Protocol methodology"
    )
    breakdown24h: dict[str, dict[str, float]] | None = Field(
        None, description="24-hour breakdown by chain"
    )
    breakdown30d: dict[str, dict[str, float]] | None = Field(
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
    allChains: list[str] = Field(..., description="List of all chains")
    protocols: list[Protocol] = Field(..., description="List of protocols")
    error: str | None = Field(None, description="Error message if any")


class DefiLlamaFetchOptionsOverview(DefiLlamaBaseTool):
    """Tool for fetching options overview data from DeFi Llama.

    This tool retrieves comprehensive data about all options protocols,
    including volume metrics, change percentages, and detailed protocol information.

    Example:
        overview_tool = DefiLlamaFetchOptionsOverview(
            ,
            agent_id="agent_123",
            agent=agent
        )
        result = await overview_tool._arun()
    """

    name: str = "defillama_fetch_options_overview"
    description: str = FETCH_OPTIONS_OVERVIEW_PROMPT

    class EmptyArgsSchema(BaseModel):
        """Empty schema for no input parameters."""

        pass

    args_schema: type[BaseModel] = EmptyArgsSchema

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
