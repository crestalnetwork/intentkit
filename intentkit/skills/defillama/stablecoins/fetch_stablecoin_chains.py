"""Tool for fetching stablecoin chains data via DeFi Llama API."""

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.base import NoArgsSchema
from intentkit.skills.defillama.api import fetch_stablecoin_chains
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_STABLECOIN_CHAINS_PROMPT = (
    """Fetch stablecoin distribution across all chains via DefiLlama."""
)


class CirculatingUSD(BaseModel):
    """Model representing circulating amounts in different pegs."""

    peggedUSD: float | None = Field(None, description="USD pegged")
    peggedEUR: float | None = Field(None, description="EUR pegged")
    peggedVAR: float | None = Field(None, description="Variable pegged")
    peggedJPY: float | None = Field(None, description="JPY pegged")
    peggedCHF: float | None = Field(None, description="CHF pegged")
    peggedCAD: float | None = Field(None, description="CAD pegged")
    peggedGBP: float | None = Field(None, description="GBP pegged")
    peggedAUD: float | None = Field(None, description="AUD pegged")
    peggedCNY: float | None = Field(None, description="CNY pegged")
    peggedREAL: float | None = Field(None, description="BRL pegged")


class ChainData(BaseModel):
    """Model representing stablecoin data for a single chain."""

    gecko_id: str | None = Field(None, description="CoinGecko ID")
    totalCirculatingUSD: CirculatingUSD = Field(
        ..., description="Circulating by peg type"
    )
    tokenSymbol: str | None = Field(None, description="Token symbol")
    name: str = Field(..., description="Chain name")


class FetchStablecoinChainsResponse(BaseModel):
    """Response schema for stablecoin chains data."""

    chains: list[ChainData] = Field(
        default_factory=list, description="Chains with stablecoin data"
    )
    error: str | None = Field(None, description="Error message")


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
    args_schema: ArgsSchema | None = NoArgsSchema  # No input parameters needed

    async def _arun(self, **kwargs) -> FetchStablecoinChainsResponse:
        """Fetch stablecoin distribution data across chains.

        Returns:
            FetchStablecoinChainsResponse containing chain data or error
        """
        # Check rate limiting
        context = self.get_context()
        is_rate_limited, error_msg = await self.check_rate_limit(context)
        if is_rate_limited:
            raise ToolException(error_msg)

        # Fetch chains data from API
        result = await fetch_stablecoin_chains()

        # Return the response matching the API structure
        return FetchStablecoinChainsResponse(chains=result)
