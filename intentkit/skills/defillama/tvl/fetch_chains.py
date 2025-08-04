"""Tool for fetching chain TVL data via DeFi Llama API."""

from typing import List, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_chains
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_CHAINS_PROMPT = """
This tool fetches current Total Value Locked (TVL) data for all blockchains tracked by DeFi Llama.
No input parameters are required. Returns a comprehensive list including:
- Chain name and identifiers
- Current TVL in USD
- Chain metadata (token symbol, IDs)
- Aggregated total TVL across all chains
Returns the complete list of chains and total TVL or an error if the request fails.
"""


class ChainTVLData(BaseModel):
    """Model representing TVL data for a single chain."""

    name: str = Field(..., description="Chain name")
    tvl: float = Field(..., description="Total Value Locked in USD")
    gecko_id: Optional[str] = Field(None, description="CoinGecko identifier")
    token_symbol: Optional[str] = Field(
        None, alias="tokenSymbol", description="Native token symbol"
    )
    cmc_id: Optional[str] = Field(
        None, alias="cmcId", description="CoinMarketCap identifier"
    )
    chain_id: Optional[int | str] = Field(
        None, alias="chainId", description="Chain identifier"
    )


class FetchChainsInput(BaseModel):
    """Input schema for fetching all chains' TVL data.

    This endpoint doesn't require any parameters as it returns
    TVL data for all chains.
    """

    pass


class FetchChainsResponse(BaseModel):
    """Response schema for all chains' TVL data."""

    chains: List[ChainTVLData] = Field(
        default_factory=list, description="List of chains with their TVL data"
    )
    total_tvl: float = Field(..., description="Total TVL across all chains in USD")
    error: Optional[str] = Field(None, description="Error message if any")


class DefiLlamaFetchChains(DefiLlamaBaseTool):
    """Tool for fetching current TVL data for all blockchains.

    This tool retrieves the current Total Value Locked (TVL) for all chains
    tracked by DeFi Llama, including chain identifiers and metadata.

    Example:
        chains_tool = DefiLlamaFetchChains(
            skill_store=store,
            agent_id="agent_123",
            agent_store=agent_store
        )
        result = await chains_tool._arun()
    """

    name: str = "defillama_fetch_chains"
    description: str = FETCH_CHAINS_PROMPT
    args_schema: Type[BaseModel] = FetchChainsInput

    async def _arun(self, **kwargs) -> FetchChainsResponse:
        """Fetch TVL data for all chains.

        Returns:
            FetchChainsResponse containing chain TVL data and total TVL or error
        """
        try:
            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return FetchChainsResponse(chains=[], total_tvl=0, error=error_msg)

            # Fetch chains data from API
            result = await fetch_chains()

            # Check for API errors
            if isinstance(result, dict) and "error" in result:
                return FetchChainsResponse(
                    chains=[], total_tvl=0, error=result["error"]
                )

            # Parse chains data and calculate total TVL
            chains = [ChainTVLData(**chain_data) for chain_data in result]
            total_tvl = sum(chain.tvl for chain in chains)

            return FetchChainsResponse(chains=chains, total_tvl=total_tvl)

        except Exception as e:
            return FetchChainsResponse(chains=[], total_tvl=0, error=str(e))
