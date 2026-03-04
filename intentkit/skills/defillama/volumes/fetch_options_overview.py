"""Tool for fetching options overview data via DeFi Llama API."""

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_options_overview
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_OPTIONS_OVERVIEW_PROMPT = """Fetch options protocols overview from DefiLlama with volumes, changes, and per-protocol data."""


class ProtocolMethodology(BaseModel):
    """Model representing protocol methodology data."""

    UserFees: str | None = Field(None, description="User fees")
    Fees: str | None = Field(None, description="Fees")
    Revenue: str | None = Field(None, description="Revenue")
    ProtocolRevenue: str | None = Field(None, description="Protocol revenue")
    HoldersRevenue: str | None = Field(None, description="Holders revenue")
    SupplySideRevenue: str | None = Field(None, description="Supply side revenue")


class Protocol(BaseModel):
    """Model representing protocol data."""

    name: str = Field(..., description="Name")
    displayName: str = Field(..., description="Display name")
    defillamaId: str = Field(..., description="DefiLlama ID")
    category: str = Field(..., description="Category")
    logo: str = Field(..., description="Logo URL")
    chains: list[str] = Field(..., description="Chains")
    module: str = Field(..., description="Module")
    total24h: float | None = Field(None, description="24h total")
    total7d: float | None = Field(None, description="7d total")
    total30d: float | None = Field(None, description="30d total")
    total1y: float | None = Field(None, description="1y total")
    totalAllTime: float | None = Field(None, description="All-time total")
    change_1d: float | None = Field(None, description="1d change %")
    change_7d: float | None = Field(None, description="7d change %")
    change_1m: float | None = Field(None, description="1m change %")
    methodology: ProtocolMethodology | None = Field(None, description="Methodology")
    breakdown24h: dict[str, dict[str, float]] | None = Field(
        None, description="24h by chain"
    )
    breakdown30d: dict[str, dict[str, float]] | None = Field(
        None, description="30d by chain"
    )


class FetchOptionsOverviewResponse(BaseModel):
    """Response schema for options overview data."""

    total24h: float = Field(..., description="24h volume")
    total7d: float = Field(..., description="7d volume")
    total30d: float = Field(..., description="30d volume")
    total1y: float = Field(..., description="1y volume")
    change_1d: float = Field(..., description="1d change %")
    change_7d: float = Field(..., description="7d change %")
    change_1m: float = Field(..., description="1m change %")
    allChains: list[str] = Field(..., description="All chains")
    protocols: list[Protocol] = Field(..., description="Protocols")
    error: str | None = Field(None, description="Error message")


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

    args_schema: ArgsSchema | None = EmptyArgsSchema

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
