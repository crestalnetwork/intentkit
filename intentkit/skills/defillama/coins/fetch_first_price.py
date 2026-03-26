"""Tool for fetching first recorded token prices via DeFi Llama API."""

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_first_price
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_FIRST_PRICE_PROMPT = """Fetch the earliest recorded price for tokens via DefiLlama. Token format: 'chain:address' or 'coingecko:id'."""


class FirstPriceData(BaseModel):
    """Model representing first price data for a single token."""

    symbol: str = Field(..., description="Symbol")
    price: float = Field(..., description="First price in USD")
    timestamp: int = Field(..., description="First recorded timestamp")


class FetchFirstPriceInput(BaseModel):
    """Input schema for fetching first token prices."""

    coins: list[str] = Field(..., description="Token IDs to query")


class FetchFirstPriceResponse(BaseModel):
    """Response schema for first token prices."""

    coins: dict[str, FirstPriceData] = Field(
        default_factory=dict, description="First prices by token ID"
    )
    error: str | None = Field(default=None, description="Error message")


class DefiLlamaFetchFirstPrice(DefiLlamaBaseTool):
    """Tool for fetching first recorded token prices from DeFi Llama.

    This tool retrieves the first price data recorded for multiple tokens,
    including the initial price, symbol, and timestamp.

    Example:
        first_price_tool = DefiLlamaFetchFirstPrice(
            ,
            agent_id="agent_123",
            agent=agent
        )
        result = await first_price_tool._arun(
            coins=["ethereum:0x...", "coingecko:ethereum"]
        )
    """

    name: str = "defillama_fetch_first_price"
    description: str = FETCH_FIRST_PRICE_PROMPT
    args_schema: ArgsSchema | None = FetchFirstPriceInput

    async def _arun(self, coins: list[str]) -> FetchFirstPriceResponse:
        """Fetch first recorded prices for the given tokens.

        Args:
            config: Runnable configuration
            coins: List of token identifiers to fetch first prices for

        Returns:
            FetchFirstPriceResponse containing first price data or error
        """
        # Check rate limiting
        context = self.get_context()
        is_rate_limited, error_msg = await self.check_rate_limit(context)
        if is_rate_limited:
            raise ToolException(error_msg)

        # Fetch first price data from API
        result = await fetch_first_price(coins=coins)

        # Return the response matching the API structure
        return FetchFirstPriceResponse(coins=result["coins"])
