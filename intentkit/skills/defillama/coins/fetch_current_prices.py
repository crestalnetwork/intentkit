"""Tool for fetching token prices via DeFi Llama API."""

from typing import Dict, List, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.defillama.api import fetch_current_prices
from intentkit.skills.defillama.base import DefiLlamaBaseTool

FETCH_PRICES_PROMPT = """
This tool fetches current token prices from DeFi Llama with a 4-hour search window.
Provide a list of token identifiers in the format:
- Ethereum tokens: 'ethereum:0x...'
- Other chains: 'chainname:0x...'
- CoinGecko IDs: 'coingecko:bitcoin'
Returns price data including:
- Current price in USD
- Token symbol
- Price confidence score
- Token decimals (if available)
- Last update timestamp
"""


class TokenPrice(BaseModel):
    """Model representing token price data."""

    price: float = Field(..., description="Current token price in USD")
    symbol: str = Field(..., description="Token symbol")
    timestamp: int = Field(..., description="Unix timestamp of last price update")
    confidence: float = Field(..., description="Confidence score for the price data")
    decimals: Optional[int] = Field(None, description="Token decimals, if available")


class FetchCurrentPricesInput(BaseModel):
    """Input schema for fetching current token prices with a 4-hour search window."""

    coins: List[str] = Field(
        ...,
        description="List of token identifiers (e.g. 'ethereum:0x...', 'coingecko:ethereum')",
    )


class FetchCurrentPricesResponse(BaseModel):
    """Response schema for current token prices."""

    coins: Dict[str, TokenPrice] = Field(
        default_factory=dict, description="Token prices keyed by token identifier"
    )
    error: Optional[str] = Field(None, description="Error message if any")


class DefiLlamaFetchCurrentPrices(DefiLlamaBaseTool):
    """Tool for fetching current token prices from DeFi Llama.

    This tool retrieves current prices for multiple tokens in a single request,
    using a 4-hour search window to ensure fresh data.

    Example:
        prices_tool = DefiLlamaFetchCurrentPrices(
            skill_store=store,
            agent_id="agent_123",
            agent_store=agent_store
        )
        result = await prices_tool._arun(
            coins=["ethereum:0x...", "coingecko:bitcoin"]
        )
    """

    name: str = "defillama_fetch_current_prices"
    description: str = FETCH_PRICES_PROMPT
    args_schema: Type[BaseModel] = FetchCurrentPricesInput

    async def _arun(self, coins: List[str]) -> FetchCurrentPricesResponse:
        """Fetch current prices for the given tokens.

        Args:
            config: Runnable configuration
            coins: List of token identifiers to fetch prices for

        Returns:
            FetchCurrentPricesResponse containing token prices or error
        """
        try:
            # Check rate limiting
            context = self.get_context()
            is_rate_limited, error_msg = await self.check_rate_limit(context)
            if is_rate_limited:
                return FetchCurrentPricesResponse(error=error_msg)

            # Fetch prices from API
            result = await fetch_current_prices(coins=coins)

            # Check for API errors
            if isinstance(result, dict) and "error" in result:
                return FetchCurrentPricesResponse(error=result["error"])

            # Return the response matching the API structure
            return FetchCurrentPricesResponse(coins=result["coins"])

        except Exception as e:
            return FetchCurrentPricesResponse(error=str(e))
