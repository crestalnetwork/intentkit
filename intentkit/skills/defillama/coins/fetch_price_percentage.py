"""Tool for fetching token price percentage changes via DeFi Llama API."""

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_price_percentage
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_PRICE_PERCENTAGE_PROMPT = """Fetch 24h price percentage changes for tokens via DefiLlama. Token format: 'chain:address' or 'coingecko:id'."""


class FetchPricePercentageInput(BaseModel):
    """Input schema for fetching token price percentage changes."""

    coins: list[str] = Field(..., description="Token IDs to query")


class FetchPricePercentageResponse(BaseModel):
    """Response schema for token price percentage changes."""

    coins: dict[str, float] = Field(
        default_factory=dict, description="24h % changes by token ID"
    )
    error: str | None = Field(None, description="Error message")


class DefiLlamaFetchPricePercentage(DefiLlamaBaseTool):
    """Tool for fetching token price percentage changes from DeFi Llama.

    This tool retrieves 24-hour price percentage changes for multiple tokens,
    calculated from the current time.

    Example:
        percentage_tool = DefiLlamaFetchPricePercentage(
            ,
            agent_id="agent_123",
            agent=agent
        )
        result = await percentage_tool._arun(
            coins=["ethereum:0x...", "coingecko:ethereum"]
        )
    """

    name: str = "defillama_fetch_price_percentage"
    description: str = FETCH_PRICE_PERCENTAGE_PROMPT
    args_schema: ArgsSchema | None = FetchPricePercentageInput

    async def _arun(self, coins: list[str]) -> FetchPricePercentageResponse:
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
