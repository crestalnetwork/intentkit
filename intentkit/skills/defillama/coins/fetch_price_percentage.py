"""Tool for fetching token price percentage changes via DeFi Llama API."""

from typing import Dict, List, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_price_percentage
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_PRICE_PERCENTAGE_PROMPT = """
This tool fetches 24-hour price percentage changes from DeFi Llama for multiple tokens.
Provide a list of token identifiers in the format:
- Ethereum tokens: 'ethereum:0x...'
- Other chains: 'chainname:0x...'
- CoinGecko IDs: 'coingecko:bitcoin'
Returns price percentage changes:
- Negative values indicate price decrease
- Positive values indicate price increase
- Changes are calculated from current time
"""


class FetchPricePercentageInput(BaseModel):
    """Input schema for fetching token price percentage changes."""

    coins: List[str] = Field(
        ..., description="List of token identifiers to fetch price changes for"
    )


class FetchPricePercentageResponse(BaseModel):
    """Response schema for token price percentage changes."""

    coins: Dict[str, float] = Field(
        default_factory=dict,
        description="Price percentage changes keyed by token identifier",
    )
    error: Optional[str] = Field(None, description="Error message if any")


class DefiLlamaFetchPricePercentage(DefiLlamaBaseTool):
    """Tool for fetching token price percentage changes from DeFi Llama.

    This tool retrieves 24-hour price percentage changes for multiple tokens,
    calculated from the current time.

    Example:
        percentage_tool = DefiLlamaFetchPricePercentage(
            skill_store=store,
            agent_id="agent_123",
            agent_store=agent_store
        )
        result = await percentage_tool._arun(
            coins=["ethereum:0x...", "coingecko:ethereum"]
        )
    """

    name: str = "defillama_fetch_price_percentage"
    description: str = FETCH_PRICE_PERCENTAGE_PROMPT
    args_schema: Type[BaseModel] = FetchPricePercentageInput

    async def _arun(self, coins: List[str]) -> FetchPricePercentageResponse:
        """Fetch price percentage changes for the given tokens.

        Args:
            config: Runnable configuration
            coins: List of token identifiers to fetch price changes for

        Returns:
            FetchPricePercentageResponse containing price percentage changes or error
        """
        try:
            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return FetchPricePercentageResponse(error=error_msg)

            # Fetch price percentage data from API
            result = await fetch_price_percentage(coins=coins)

            # Check for API errors
            if isinstance(result, dict) and "error" in result:
                return FetchPricePercentageResponse(error=result["error"])

            # Return the response matching the API structure
            return FetchPricePercentageResponse(coins=result["coins"])

        except Exception as e:
            return FetchPricePercentageResponse(error=str(e))
