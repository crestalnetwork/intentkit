"""Tool for fetching chain historical TVL via DeFiLlama API."""

from typing import List, Type

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_chain_historical_tvl
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_HISTORICAL_TVL_PROMPT = """
This tool fetches historical Total Value Locked (TVL) data for a specific blockchain.
Provide the chain name (e.g., "ethereum", "solana") to get its TVL history.
Returns a time series of TVL values with their corresponding dates.
"""


class HistoricalTVLDataPoint(BaseModel):
    """Model representing a single TVL data point."""

    date: int = Field(..., description="Unix timestamp of the TVL measurement")
    tvl: float = Field(..., description="Total Value Locked in USD at this timestamp")


class FetchChainHistoricalTVLInput(BaseModel):
    """Input schema for fetching chain-specific historical TVL data."""

    chain: str = Field(
        ..., description="Chain name to fetch TVL for (e.g., 'ethereum', 'solana')"
    )


class FetchChainHistoricalTVLResponse(BaseModel):
    """Response schema for chain-specific historical TVL data."""

    chain: str = Field(..., description="Normalized chain name")
    data: List[HistoricalTVLDataPoint] = Field(
        default_factory=list, description="List of historical TVL data points"
    )
    error: str | None = Field(default=None, description="Error message if any")


class DefiLlamaFetchChainHistoricalTvl(DefiLlamaBaseTool):
    """Tool for fetching historical TVL data for a specific blockchain.

    This tool fetches the complete Total Value Locked (TVL) history for a given
    blockchain using the DeFiLlama API. It includes rate limiting and chain
    validation to ensure reliable data retrieval.

    Example:
        tvl_tool = DefiLlamaFetchChainHistoricalTvl(
            skill_store=store,
            agent_id="agent_123",
            agent_store=agent_store
        )
        result = await tvl_tool._arun(chain="ethereum")
    """

    name: str = "defillama_fetch_chain_historical_tvl"
    description: str = FETCH_HISTORICAL_TVL_PROMPT
    args_schema: Type[BaseModel] = FetchChainHistoricalTVLInput

    async def _arun(self, chain: str) -> FetchChainHistoricalTVLResponse:
        """Fetch historical TVL data for the given chain.

        Args:
            config: Runnable configuration
            chain: Blockchain name (e.g., "ethereum", "solana")

        Returns:
            FetchChainHistoricalTVLResponse containing chain name, TVL history or error
        """
        try:
            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return FetchChainHistoricalTVLResponse(chain=chain, error=error_msg)

            # Validate chain parameter
            is_valid, normalized_chain = await self.validate_chain(chain)
            if not is_valid or normalized_chain is None:
                return FetchChainHistoricalTVLResponse(
                    chain=chain, error=f"Invalid chain: {chain}"
                )

            # Fetch TVL history from API
            result = await fetch_chain_historical_tvl(normalized_chain)

            # Check for API errors
            if isinstance(result, dict) and "error" in result:
                return FetchChainHistoricalTVLResponse(
                    chain=normalized_chain, error=result["error"]
                )

            # Parse response into our schema
            data_points = [HistoricalTVLDataPoint(**point) for point in result]

            return FetchChainHistoricalTVLResponse(
                chain=normalized_chain, data=data_points
            )

        except Exception as e:
            return FetchChainHistoricalTVLResponse(chain=chain, error=str(e))
