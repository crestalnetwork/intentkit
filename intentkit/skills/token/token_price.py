import logging
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.token.base import TokenBaseTool
from intentkit.skills.token.constants import DEFAULT_CHAIN

logger = logging.getLogger(__name__)


class TokenPriceInput(BaseModel):
    """Input for token price tool."""

    address: str = Field(
        description="The address of the token contract to get price for."
    )
    chain: str = Field(
        description="The chain to query (e.g., 'eth', 'bsc', 'polygon').",
        default=DEFAULT_CHAIN,
    )
    include: Optional[str] = Field(
        description="If the result should contain the 24hr percent change (use 'percent_change').",
        default=None,
    )
    exchange: Optional[str] = Field(
        description="The factory name or address of the token exchange.",
        default=None,
    )
    to_block: Optional[int] = Field(
        description="The block number from which the token price should be checked.",
        default=None,
    )
    max_token_inactivity: Optional[int] = Field(
        description="Exclude tokens inactive for more than the given amount of days.",
        default=None,
    )
    min_pair_side_liquidity_usd: Optional[int] = Field(
        description="Exclude tokens with liquidity less than the specified amount in USD.",
        default=None,
    )


class TokenPrice(TokenBaseTool):
    """Tool for retrieving ERC20 token prices using Moralis.

    This tool uses Moralis' API to fetch the token price denominated in the blockchain's native token
    and USD for a given token contract address.
    """

    name: str = "token_price"
    description: str = (
        "Get the token price denominated in the blockchain's native token and USD for a given token contract address. "
        "Returns price, token information and exchange data."
    )
    args_schema: Type[BaseModel] = TokenPriceInput

    async def _arun(
        self,
        address: str,
        chain: str = DEFAULT_CHAIN,
        include: Optional[str] = None,
        exchange: Optional[str] = None,
        to_block: Optional[int] = None,
        max_token_inactivity: Optional[int] = None,
        min_pair_side_liquidity_usd: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
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
        params = {"chain": chain}

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
                logger.error(f"API returned error: {response.get('error')}")

            return response
        except Exception as e:
            logger.error(f"Error fetching token price: {e}")
            return {
                "error": f"An error occurred while fetching token price: {str(e)}. Please try again later."
            }
