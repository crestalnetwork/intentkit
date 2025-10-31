"""Tool for fetching stablecoin chains data via DeFi Llama API."""

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_stablecoin_chains
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_STABLECOIN_CHAINS_PROMPT = """
This tool fetches stablecoin distribution data across all chains from DeFi Llama.
Returns:
- List of chains with stablecoin circulating amounts
- Token information for each chain
- Peg type circulating amounts (USD, EUR, etc.)
"""


class CirculatingUSD(BaseModel):
    """Model representing circulating amounts in different pegs."""

    peggedUSD: float | None = Field(None, description="Amount pegged to USD")
    peggedEUR: float | None = Field(None, description="Amount pegged to EUR")
    peggedVAR: float | None = Field(None, description="Amount in variable pegs")
    peggedJPY: float | None = Field(None, description="Amount pegged to JPY")
    peggedCHF: float | None = Field(None, description="Amount pegged to CHF")
    peggedCAD: float | None = Field(None, description="Amount pegged to CAD")
    peggedGBP: float | None = Field(None, description="Amount pegged to GBP")
    peggedAUD: float | None = Field(None, description="Amount pegged to AUD")
    peggedCNY: float | None = Field(None, description="Amount pegged to CNY")
    peggedREAL: float | None = Field(
        None, description="Amount pegged to Brazilian Real"
    )


class ChainData(BaseModel):
    """Model representing stablecoin data for a single chain."""

    gecko_id: str | None = Field(None, description="CoinGecko ID of the chain")
    totalCirculatingUSD: CirculatingUSD = Field(
        ..., description="Total circulating amounts in different pegs"
    )
    tokenSymbol: str | None = Field(None, description="Native token symbol")
    name: str = Field(..., description="Chain name")


class FetchStablecoinChainsResponse(BaseModel):
    """Response schema for stablecoin chains data."""

    chains: list[ChainData] = Field(
        default_factory=list, description="List of chains with their stablecoin data"
    )
    error: str | None = Field(None, description="Error message if any")


class DefiLlamaFetchStablecoinChains(DefiLlamaBaseTool):
    """Tool for fetching stablecoin distribution across chains from DeFi Llama.

    This tool retrieves data about how stablecoins are distributed across different
    blockchain networks, including circulation amounts and token information.

    Example:
        chains_tool = DefiLlamaFetchStablecoinChains(
            ,
            agent_id="agent_123",
            agent=agent
        )
        result = await chains_tool._arun()
    """

    name: str = "defillama_fetch_stablecoin_chains"
    description: str = FETCH_STABLECOIN_CHAINS_PROMPT
    args_schema: None = None  # No input parameters needed

    async def _arun(self, **kwargs) -> FetchStablecoinChainsResponse:
        """Fetch stablecoin distribution data across chains.

        Returns:
            FetchStablecoinChainsResponse containing chain data or error
        """
        try:
            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return FetchStablecoinChainsResponse(error=error_msg)

            # Fetch chains data from API
            result = await fetch_stablecoin_chains()

            # Check for API errors
            if isinstance(result, dict) and "error" in result:
                return FetchStablecoinChainsResponse(error=result["error"])

            # Return the response matching the API structure
            return FetchStablecoinChainsResponse(chains=result)

        except Exception as e:
            return FetchStablecoinChainsResponse(error=str(e))
