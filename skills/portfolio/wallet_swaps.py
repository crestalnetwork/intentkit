import logging
from typing import Any, Dict, List, Optional, Type

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from skills.portfolio.base import PortfolioBaseTool
from skills.portfolio.constants import (
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
    cursor: Optional[str] = Field(
        description="The cursor for pagination.",
        default=None,
    )
    limit: Optional[int] = Field(
        description="The number of results per page.",
        default=DEFAULT_LIMIT,
    )
    from_block: Optional[str] = Field(
        description="The minimum block number to get transactions from.",
        default=None,
    )
    to_block: Optional[str] = Field(
        description="The maximum block number to get transactions from.",
        default=None,
    )
    from_date: Optional[str] = Field(
        description="The start date to get transactions from (format in seconds or datestring).",
        default=None,
    )
    to_date: Optional[str] = Field(
        description="The end date to get transactions from (format in seconds or datestring).",
        default=None,
    )
    order: Optional[str] = Field(
        description="The order of the result (ASC or DESC).",
        default=DEFAULT_ORDER,
    )
    transaction_types: Optional[List[str]] = Field(
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
    args_schema: Type[BaseModel] = WalletSwapsInput

    async def _arun(
        self,
        address: str,
        chain: str = DEFAULT_CHAIN,
        cursor: Optional[str] = None,
        limit: Optional[int] = DEFAULT_LIMIT,
        from_block: Optional[str] = None,
        to_block: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        order: Optional[str] = DEFAULT_ORDER,
        transaction_types: Optional[List[str]] = None,
        config: RunnableConfig = None,
        **kwargs,
    ) -> Dict[str, Any]:
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
        context = self.context_from_config(config)
        logger.debug(f"wallet_swaps.py: Fetching wallet swaps with context {context}")

        # Get the API key from the agent's configuration
        api_key = self.get_api_key(context)
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
