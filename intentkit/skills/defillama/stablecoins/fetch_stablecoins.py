"""Tool for fetching stablecoin data via DeFi Llama API."""

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.base import NoArgsSchema
from intentkit.skills.defillama.api import fetch_stablecoins
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_STABLECOINS_PROMPT = """Fetch all stablecoins data from DefiLlama including supply, prices, and peg info."""


class CirculatingAmount(BaseModel):
    """Model representing circulating amounts for a specific peg type."""

    peggedUSD: float = Field(..., description="USD pegged amount")


class ChainCirculating(BaseModel):
    """Model representing circulating amounts on a specific chain."""

    current: CirculatingAmount = Field(..., description="Current")
    circulatingPrevDay: CirculatingAmount = Field(..., description="Previous day")
    circulatingPrevWeek: CirculatingAmount = Field(..., description="Previous week")
    circulatingPrevMonth: CirculatingAmount = Field(..., description="Previous month")


class Stablecoin(BaseModel):
    """Model representing a single stablecoin's data."""

    id: str = Field(..., description="ID")
    name: str = Field(..., description="Name")
    symbol: str = Field(..., description="Symbol")
    gecko_id: str | None = Field(None, description="CoinGecko ID")
    pegType: str = Field(..., description="Peg type")
    priceSource: str = Field(..., description="Price source")
    pegMechanism: str = Field(..., description="Peg mechanism")
    circulating: CirculatingAmount = Field(..., description="Current circulating")
    circulatingPrevDay: CirculatingAmount = Field(..., description="Previous day")
    circulatingPrevWeek: CirculatingAmount = Field(..., description="Previous week")
    circulatingPrevMonth: CirculatingAmount = Field(..., description="Previous month")
    chainCirculating: dict[str, ChainCirculating] = Field(
        ..., description="Per-chain circulating"
    )
    chains: list[str] = Field(..., description="Chains present on")
    price: float = Field(..., description="Price in USD")


class FetchStablecoinsResponse(BaseModel):
    """Response schema for stablecoin data."""

    peggedAssets: list[Stablecoin] = Field(
        default_factory=list, description="Stablecoins"
    )
    error: str | None = Field(None, description="Error message")


class DefiLlamaFetchStablecoins(DefiLlamaBaseTool):
    """Tool for fetching stablecoin data from DeFi Llama.

    This tool retrieves comprehensive data about stablecoins, including their
    circulating supply across different chains, price information, and peg details.

    Example:
        stablecoins_tool = DefiLlamaFetchStablecoins(
            ,
            agent_id="agent_123",
            agent=agent
        )
        result = await stablecoins_tool._arun()
    """

    name: str = "defillama_fetch_stablecoins"
    description: str = FETCH_STABLECOINS_PROMPT
    args_schema: ArgsSchema | None = NoArgsSchema  # No input parameters needed

    async def _arun(self, **kwargs) -> FetchStablecoinsResponse:
        """Fetch stablecoin data.

        Returns:
            FetchStablecoinsResponse containing stablecoin data or error
        """
        try:
            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return FetchStablecoinsResponse(error=error_msg)

            # Fetch stablecoin data from API
            result = await fetch_stablecoins()

            # Check for API errors
            if isinstance(result, dict) and "error" in result:
                return FetchStablecoinsResponse(error=result["error"])

            # Return the response matching the API structure
            return FetchStablecoinsResponse(**result)

        except Exception as e:
            return FetchStablecoinsResponse(error=str(e))
