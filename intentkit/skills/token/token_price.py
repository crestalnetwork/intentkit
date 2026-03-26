import logging
from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.token.base import TokenBaseTool
from intentkit.skills.token.constants import DEFAULT_CHAIN

logger = logging.getLogger(__name__)


class TokenPriceInput(BaseModel):
    """Input for token price tool."""

    address: str = Field(description="Token contract address.")
    chain: str = Field(
        description="Chain to query, e.g. 'eth', 'bsc', 'polygon'.",
        default=DEFAULT_CHAIN,
    )
    include: str | None = Field(
        description="Set to 'percent_change' for 24hr change.",
        default=None,
    )
    exchange: str | None = Field(
        description="Exchange name or address.",
        default=None,
    )
    to_block: int | None = Field(
        description="Block number for price check.",
        default=None,
    )
    max_token_inactivity: int | None = Field(
        description="Max inactive days to exclude.",
        default=None,
    )
    min_pair_side_liquidity_usd: int | None = Field(
        description="Min liquidity in USD.",
        default=None,
    )


class TokenPrice(TokenBaseTool):
    """Tool for retrieving ERC20 token prices using Moralis.

    This tool uses Moralis' API to fetch the token price denominated in the blockchain's native token
    and USD for a given token contract address.
    """

    name: str = "token_price"
    description: str = "Get token price in native currency and USD."
    args_schema: ArgsSchema | None = TokenPriceInput

    async def _arun(
        self,
        address: str,
        chain: str = DEFAULT_CHAIN,
        include: str | None = None,
        exchange: str | None = None,
        to_block: int | None = None,
        max_token_inactivity: int | None = None,
        min_pair_side_liquidity_usd: int | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Fetch token price from Moralis.

        Args:
            address: The token contract address
            chain: The blockchain to query
            include: Include 24hr percent change
            exchange: The token exchange factory name or address
            to_block: Block number to check price from
            max_token_inactivity: Max days of inactivity to exclude tokens
            min_pair_side_liquidity_usd: Min liquidity in USD to include
            config: The configuration for the tool call

        Returns:
            Dict containing token price data
        """
        # Extract context from config
        context = self.get_context()

        if context is None:
            logger.error("Context is None, cannot retrieve API key")
            return {
                "error": "Cannot retrieve API key. Please check agent configuration."
            }

        # Get the API key
        api_key = self.get_api_key()

        if not api_key:
            logger.error("No Moralis API key available")
            return {"error": "No Moralis API key provided in the configuration."}

        # Build query parameters
        params: dict[str, Any] = {"chain": chain}

        # Add optional parameters if they exist
        if include:
            params["include"] = include
        if exchange:
            params["exchange"] = exchange
        if to_block:
            params["to_block"] = to_block
        if max_token_inactivity:
            params["max_token_inactivity"] = max_token_inactivity
        if min_pair_side_liquidity_usd:
            params["min_pair_side_liquidity_usd"] = min_pair_side_liquidity_usd

        # Call Moralis API
        try:
            endpoint = f"/erc20/{address}/price"
            response = await self._make_request(
                method="GET", endpoint=endpoint, api_key=api_key, params=params
            )

            if "error" in response:
                logger.error("API returned error: %s", response.get("error"))

            return response
        except Exception as e:
            logger.error("Error fetching token price: %s", e)
            return {
                "error": f"An error occurred while fetching token price: {str(e)}. Please try again later."
            }
