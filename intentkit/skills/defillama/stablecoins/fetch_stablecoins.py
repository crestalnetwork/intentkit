"""Tool for fetching stablecoin data via DeFi Llama API."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_stablecoins
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_STABLECOINS_PROMPT = """
This tool fetches comprehensive stablecoin data from DeFi Llama.
Returns:
- List of stablecoins with details like name, symbol, market cap
- Per-chain circulating amounts
- Historical circulating amounts (day/week/month)
- Current prices and price history
- Peg mechanism and type information
"""


class CirculatingAmount(BaseModel):
    """Model representing circulating amounts for a specific peg type."""

    peggedUSD: float = Field(..., description="Amount pegged to USD")


class ChainCirculating(BaseModel):
    """Model representing circulating amounts on a specific chain."""

    current: CirculatingAmount = Field(..., description="Current circulating amount")
    circulatingPrevDay: CirculatingAmount = Field(
        ..., description="Circulating amount from previous day"
    )
    circulatingPrevWeek: CirculatingAmount = Field(
        ..., description="Circulating amount from previous week"
    )
    circulatingPrevMonth: CirculatingAmount = Field(
        ..., description="Circulating amount from previous month"
    )


class Stablecoin(BaseModel):
    """Model representing a single stablecoin's data."""

    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Stablecoin name")
    symbol: str = Field(..., description="Token symbol")
    gecko_id: Optional[str] = Field(None, description="CoinGecko ID if available")
    pegType: str = Field(..., description="Type of peg (e.g. peggedUSD)")
    priceSource: str = Field(..., description="Source of price data")
    pegMechanism: str = Field(..., description="Mechanism maintaining the peg")
    circulating: CirculatingAmount = Field(
        ..., description="Current total circulating amount"
    )
    circulatingPrevDay: CirculatingAmount = Field(
        ..., description="Total circulating amount from previous day"
    )
    circulatingPrevWeek: CirculatingAmount = Field(
        ..., description="Total circulating amount from previous week"
    )
    circulatingPrevMonth: CirculatingAmount = Field(
        ..., description="Total circulating amount from previous month"
    )
    chainCirculating: Dict[str, ChainCirculating] = Field(
        ..., description="Circulating amounts per chain"
    )
    chains: List[str] = Field(
        ..., description="List of chains where the stablecoin is present"
    )
    price: float = Field(..., description="Current price in USD")


class FetchStablecoinsResponse(BaseModel):
    """Response schema for stablecoin data."""

    peggedAssets: List[Stablecoin] = Field(
        default_factory=list, description="List of stablecoins with their data"
    )
    error: Optional[str] = Field(None, description="Error message if any")


class DefiLlamaFetchStablecoins(DefiLlamaBaseTool):
    """Tool for fetching stablecoin data from DeFi Llama.

    This tool retrieves comprehensive data about stablecoins, including their
    circulating supply across different chains, price information, and peg details.

    Example:
        stablecoins_tool = DefiLlamaFetchStablecoins(
            skill_store=store,
            agent_id="agent_123",
            agent_store=agent_store
        )
        result = await stablecoins_tool._arun()
    """

    name: str = "defillama_fetch_stablecoins"
    description: str = FETCH_STABLECOINS_PROMPT
    args_schema: None = None  # No input parameters needed

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
