import logging
from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.portfolio.base import PortfolioBaseTool
from intentkit.skills.portfolio.constants import (
    DEFAULT_CHAIN,
    DEFAULT_LIMIT,
)

logger = logging.getLogger(__name__)


class TokenBalancesInput(BaseModel):
    """Input for token balances tool."""

    address: str = Field(description="Wallet address.")
    chain: str = Field(
        description="Chain to query.",
        default=DEFAULT_CHAIN,
    )
    to_block: int | None = Field(
        description="Max block number for balances.",
        default=None,
    )
    token_addresses: list[str] | None = Field(
        description="Filter by token addresses.",
        default=None,
    )
    exclude_spam: bool | None = Field(
        description="Exclude spam tokens.",
        default=True,
    )
    exclude_unverified_contracts: bool | None = Field(
        description="Exclude unverified contracts.",
        default=True,
    )
    cursor: str | None = Field(
        description="Pagination cursor.",
        default=None,
    )
    limit: int | None = Field(
        description="Results per page.",
        default=DEFAULT_LIMIT,
    )
    exclude_native: bool | None = Field(
        description="Exclude native balance.",
        default=None,
    )
    max_token_inactivity: int | None = Field(
        description="Exclude tokens inactive for more than N days.",
        default=None,
    )
    min_pair_side_liquidity_usd: float | None = Field(
        description="Min liquidity in USD to include token.",
        default=None,
    )


class TokenBalances(PortfolioBaseTool):
    """Tool for retrieving native and ERC20 token balances using Moralis.

    This tool uses Moralis' API to fetch token balances for a specific wallet address
    and their token prices in USD.
    """

    name: str = "portfolio_token_balances"
    description: str = "Get token balances and prices in USD for a wallet address."
    args_schema: ArgsSchema | None = TokenBalancesInput

    async def _arun(
        self,
        address: str,
        chain: str = DEFAULT_CHAIN,
        to_block: int | None = None,
        token_addresses: list[str] | None = None,
        exclude_spam: bool | None = True,
        exclude_unverified_contracts: bool | None = True,
        cursor: str | None = None,
        limit: int | None = DEFAULT_LIMIT,
        exclude_native: bool | None = None,
        max_token_inactivity: int | None = None,
        min_pair_side_liquidity_usd: float | None = None,
        **kwargs,
    ) -> dict[str, Any]:
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
