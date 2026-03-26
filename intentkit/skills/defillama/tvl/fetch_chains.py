"""Tool for fetching chain TVL data via DeFi Llama API."""

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_chains
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_CHAINS_PROMPT = """Fetch current TVL for all chains tracked by DefiLlama."""


class ChainTVLData(BaseModel):
    """Model representing TVL data for a single chain."""

    name: str = Field(..., description="Chain name")
    tvl: float = Field(..., description="TVL in USD")
    gecko_id: str | None = Field(None, description="CoinGecko ID")
    token_symbol: str | None = Field(
        None, alias="tokenSymbol", description="Token symbol"
    )
    cmc_id: str | None = Field(None, alias="cmcId", description="CMC ID")
    chain_id: int | str | None = Field(None, alias="chainId", description="Chain ID")


class FetchChainsInput(BaseModel):
    """Input schema for fetching all chains' TVL data.

    This endpoint doesn't require any parameters as it returns
    TVL data for all chains.
    """

    pass


class FetchChainsResponse(BaseModel):
    """Response schema for all chains' TVL data."""

    chains: list[ChainTVLData] = Field(
        default_factory=list, description="Chains with TVL"
    )
    total_tvl: float = Field(..., description="Total TVL in USD")
    error: str | None = Field(default=None, description="Error message")


class DefiLlamaFetchChains(DefiLlamaBaseTool):
    """Tool for fetching current TVL data for all blockchains.

    This tool retrieves the current Total Value Locked (TVL) for all chains
    tracked by DeFi Llama, including chain identifiers and metadata.

    Example:
        chains_tool = DefiLlamaFetchChains(
            ,
            agent_id="agent_123",
            agent=agent
        )
        result = await chains_tool._arun()
    """

    name: str = "defillama_fetch_chains"
    description: str = FETCH_CHAINS_PROMPT
    args_schema: ArgsSchema | None = FetchChainsInput

    async def _arun(self, **kwargs) -> FetchChainsResponse:
        """Fetch TVL data for all chains.

        Returns:
            FetchChainsResponse containing chain TVL data and total TVL or error
        """
        # Check rate limiting
        context = self.get_context()
        is_rate_limited, error_msg = await self.check_rate_limit(context)
        if is_rate_limited:
            raise ToolException(error_msg)

        # Fetch chains data from API
        result = await fetch_chains()

        # Parse chains data and calculate total TVL
        chains = [ChainTVLData(**chain_data) for chain_data in result]
        total_tvl = sum(chain.tvl for chain in chains)

        return FetchChainsResponse(chains=chains, total_tvl=total_tvl)
