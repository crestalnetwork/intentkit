import logging
from typing import Any

from pydantic import BaseModel, Field

from intentkit.skills.portfolio.base import PortfolioBaseTool
from intentkit.skills.portfolio.constants import (
    DEFAULT_CHAIN,
    DEFAULT_LIMIT,
    DEFAULT_ORDER,
)

logger = logging.getLogger(__name__)


class WalletSwapsInput(BaseModel):
    """Input for wallet swaps tool."""

    address: str = Field(description="The wallet address to get swap transactions for.")
    chain: str = Field(
        description="The chain to query (e.g., 'eth', 'bsc', 'polygon').",
        default=DEFAULT_CHAIN,
    )
    cursor: str | None = Field(
        description="The cursor for pagination.",
        default=None,
    )
    limit: int | None = Field(
        description="The number of results per page.",
        default=DEFAULT_LIMIT,
    )
    from_block: str | None = Field(
        description="The minimum block number to get transactions from.",
        default=None,
    )
    to_block: str | None = Field(
        description="The maximum block number to get transactions from.",
        default=None,
    )
    from_date: str | None = Field(
        description="The start date to get transactions from (format in seconds or datestring).",
        default=None,
    )
    to_date: str | None = Field(
        description="The end date to get transactions from (format in seconds or datestring).",
        default=None,
    )
    order: str | None = Field(
        description="The order of the result (ASC or DESC).",
        default=DEFAULT_ORDER,
    )
    transaction_types: list[str] | None = Field(
        description="Array of transaction types. Allowed values are 'buy', 'sell'.",
        default=None,
    )


class WalletSwaps(PortfolioBaseTool):
    """Tool for retrieving swap-related transactions for a wallet using Moralis.

    This tool uses Moralis' API to fetch all swap-related (buy, sell) transactions
    for a specific wallet address.
    """

    name: str = "portfolio_wallet_swaps"
    description: str = (
        "Get all swap-related transactions (buy, sell) for a wallet address. "
        "Note that swaps data is only available from September 2024 onwards."
    )
    args_schema: type[BaseModel] = WalletSwapsInput

    async def _arun(
        self,
        address: str,
        chain: str = DEFAULT_CHAIN,
        cursor: str | None = None,
        limit: int | None = DEFAULT_LIMIT,
        from_block: str | None = None,
        to_block: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        order: str | None = DEFAULT_ORDER,
        transaction_types: list[str] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Fetch wallet swap transactions from Moralis.

        Args:
            address: The wallet address to get swaps for
            chain: The blockchain to query
            cursor: Pagination cursor
            limit: Number of results per page
            from_block: Minimum block number for transactions
            to_block: Maximum block number for transactions
            from_date: Start date for transactions
            to_date: End date for transactions
            order: Order of results (ASC/DESC)
            transaction_types: Types of transactions to include ('buy', 'sell')
            config: The configuration for the tool call

        Returns:
            Dict containing wallet swaps data
        """
        context = self.get_context()
        logger.debug(f"wallet_swaps.py: Fetching wallet swaps with context {context}")

        # Get the API key from the agent's configuration
        api_key = self.get_api_key()
        if not api_key:
            return {"error": "No Moralis API key provided in the configuration."}

        # Build query parameters
        params = {
            "chain": chain,
            "limit": limit,
            "order": order,
        }

        # Add optional parameters if they exist
        if cursor:
            params["cursor"] = cursor
        if from_block:
            params["fromBlock"] = from_block
        if to_block:
            params["toBlock"] = to_block
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date
        if transaction_types:
            params["transactionTypes"] = transaction_types

        # Call Moralis API
        try:
            endpoint = f"/wallets/{address}/swaps"
            return await self._make_request(
                method="GET", endpoint=endpoint, api_key=api_key, params=params
            )
        except Exception as e:
            logger.error(
                f"wallet_swaps.py: Error fetching wallet swaps: {e}", exc_info=True
            )
            return {
                "error": "An error occurred while fetching wallet swaps. Please try again later."
            }
