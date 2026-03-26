"""Tool for fetching fees overview data via DeFi Llama API."""

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_fees_overview
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_FEES_OVERVIEW_PROMPT = """Fetch protocol fees overview from DefiLlama, including totals, changes, and per-protocol breakdowns."""


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
    category: str = Field(..., description="Category")
    logo: str = Field(..., description="Logo URL")
    chains: list[str] = Field(..., description="Chains")
    module: str = Field(..., description="Module")
    total24h: float | None = Field(None, description="24h fees")
    total7d: float | None = Field(None, description="7d fees")
    total30d: float | None = Field(None, description="30d fees")
    total1y: float | None = Field(None, description="1y fees")
    totalAllTime: float | None = Field(None, description="All-time fees")
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


class FetchFeesOverviewResponse(BaseModel):
    """Response schema for fees overview data."""

    total24h: float = Field(..., description="24h total fees")
    total7d: float = Field(..., description="7d total fees")
    total30d: float = Field(..., description="30d total fees")
    total1y: float = Field(..., description="1y total fees")
    change_1d: float = Field(..., description="1d change %")
    change_7d: float = Field(..., description="7d change %")
    change_1m: float = Field(..., description="1m change %")
    allChains: list[str] = Field(..., description="All chains")
    protocols: list[Protocol] = Field(..., description="Protocols")
    error: str | None = Field(None, description="Error message")


class DefiLlamaFetchFeesOverview(DefiLlamaBaseTool):
    """Tool for fetching fees overview data from DeFi Llama.

    This tool retrieves comprehensive data about protocol fees,
    including fee metrics, change percentages, and detailed protocol information.

    Example:
        overview_tool = DefiLlamaFetchFeesOverview(
            ,
            agent_id="agent_123",
            agent=agent
        )
        result = await overview_tool._arun()
    """

    name: str = "defillama_fetch_fees_overview"
    description: str = FETCH_FEES_OVERVIEW_PROMPT

    class EmptyArgsSchema(BaseModel):
        """Empty schema for no input parameters."""

        pass

    args_schema: ArgsSchema | None = EmptyArgsSchema

    async def _arun(self, **kwargs) -> FetchFeesOverviewResponse:
        """Fetch overview data for protocol fees.

        Returns:
            FetchFeesOverviewResponse containing comprehensive fee data or error
        """
        # Check rate limiting
        context = self.get_context()
        is_rate_limited, error_msg = await self.check_rate_limit(context)
        if is_rate_limited:
            raise ToolException(error_msg)

        # Fetch fees data from API
        result = await fetch_fees_overview()

        # Return the parsed response
        return FetchFeesOverviewResponse(**result)
