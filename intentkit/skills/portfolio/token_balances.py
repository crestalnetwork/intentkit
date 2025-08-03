import logging
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.portfolio.base import PortfolioBaseTool
from intentkit.skills.portfolio.constants import (
    DEFAULT_CHAIN,
    DEFAULT_LIMIT,
)

logger = logging.getLogger(__name__)


class TokenBalancesInput(BaseModel):
    """Input for token balances tool."""

    address: str = Field(description="The wallet address to check token balances for.")
    chain: str = Field(
        description="The chain to query (e.g., 'eth', 'bsc', 'polygon').",
        default=DEFAULT_CHAIN,
    )
    to_block: Optional[int] = Field(
        description="The block number up to which the balances will be checked.",
        default=None,
    )
    token_addresses: Optional[List[str]] = Field(
        description="The specific token addresses to get balances for.",
        default=None,
    )
    exclude_spam: Optional[bool] = Field(
        description="Exclude spam tokens from the result.",
        default=True,
    )
    exclude_unverified_contracts: Optional[bool] = Field(
        description="Exclude unverified contracts from the result.",
        default=True,
    )
    cursor: Optional[str] = Field(
        description="The cursor for pagination.",
        default=None,
    )
    limit: Optional[int] = Field(
        description="The number of results per page.",
        default=DEFAULT_LIMIT,
    )
    exclude_native: Optional[bool] = Field(
        description="Exclude native balance from the result.",
        default=None,
    )
    max_token_inactivity: Optional[int] = Field(
        description="Exclude tokens inactive for more than the given amount of days.",
        default=None,
    )
    min_pair_side_liquidity_usd: Optional[float] = Field(
        description="Exclude tokens with liquidity less than the specified amount in USD.",
        default=None,
    )


class TokenBalances(PortfolioBaseTool):
    """Tool for retrieving native and ERC20 token balances using Moralis.

    This tool uses Moralis' API to fetch token balances for a specific wallet address
    and their token prices in USD.
    """

    name: str = "portfolio_token_balances"
    description: str = (
        "Get token balances for a specific wallet address and their token prices in USD. "
        "Includes options to exclude spam and unverified contracts."
    )
    args_schema: Type[BaseModel] = TokenBalancesInput

    async def _arun(
        self,
        address: str,
        chain: str = DEFAULT_CHAIN,
        to_block: Optional[int] = None,
        token_addresses: Optional[List[str]] = None,
        exclude_spam: Optional[bool] = True,
        exclude_unverified_contracts: Optional[bool] = True,
        cursor: Optional[str] = None,
        limit: Optional[int] = DEFAULT_LIMIT,
        exclude_native: Optional[bool] = None,
        max_token_inactivity: Optional[int] = None,
        min_pair_side_liquidity_usd: Optional[float] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Fetch token balances from Moralis.

        Args:
            address: The wallet address to get balances for
            chain: The blockchain to query
            to_block: Block number up to which balances will be checked
            token_addresses: Specific token addresses to get balances for
            exclude_spam: Whether to exclude spam tokens
            exclude_unverified_contracts: Whether to exclude unverified contracts
            cursor: Pagination cursor
            limit: Number of results per page
            exclude_native: Whether to exclude native balance
            max_token_inactivity: Exclude tokens inactive for more than the given days
            min_pair_side_liquidity_usd: Exclude tokens with liquidity less than specified
            config: The configuration for the tool call

        Returns:
            Dict containing token balances data
        """
        context = self.get_context()
        logger.debug(
            f"token_balances.py: Fetching token balances with context {context}"
        )

        # Get the API key from the agent's configuration
        api_key = self.get_api_key()
        if not api_key:
            return {"error": "No Moralis API key provided in the configuration."}

        # Build query parameters
        params = {
            "chain": chain,
            "limit": limit,
            "exclude_spam": exclude_spam,
            "exclude_unverified_contracts": exclude_unverified_contracts,
        }

        # Add optional parameters if they exist
        if to_block:
            params["to_block"] = to_block
        if token_addresses:
            params["token_addresses"] = token_addresses
        if cursor:
            params["cursor"] = cursor
        if exclude_native is not None:
            params["exclude_native"] = exclude_native
        if max_token_inactivity:
            params["max_token_inactivity"] = max_token_inactivity
        if min_pair_side_liquidity_usd:
            params["min_pair_side_liquidity_usd"] = min_pair_side_liquidity_usd

        # Call Moralis API
        try:
            endpoint = f"/wallets/{address}/tokens"
            return await self._make_request(
                method="GET", endpoint=endpoint, api_key=api_key, params=params
            )
        except Exception as e:
            logger.error(
                f"token_balances.py: Error fetching token balances: {e}", exc_info=True
            )
            return {
                "error": "An error occurred while fetching token balances. Please try again later."
            }
