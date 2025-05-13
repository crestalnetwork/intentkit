import logging
from typing import Any, Dict, Optional, Type

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from skills.portfolio.base import PortfolioBaseTool
from skills.portfolio.constants import (
    DEFAULT_CHAIN,
    DEFAULT_LIMIT,
    DEFAULT_ORDER,
)

logger = logging.getLogger(__name__)


class WalletHistoryInput(BaseModel):
    """Input for wallet transaction history tool."""

    address: str = Field(
        description="The address of the wallet to get transaction history for."
    )
    chain: str = Field(
        description="The chain to query (e.g., 'eth', 'bsc', 'polygon').",
        default=DEFAULT_CHAIN,
    )
    limit: Optional[int] = Field(
        description="The desired page size of the result.",
        default=DEFAULT_LIMIT,
    )
    cursor: Optional[str] = Field(
        description="The cursor returned in the previous response (for pagination).",
        default=None,
    )
    from_block: Optional[int] = Field(
        description="The minimum block number to get transactions from.",
        default=None,
    )
    to_block: Optional[int] = Field(
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
    include_internal_transactions: Optional[bool] = Field(
        description="If the result should contain the internal transactions.",
        default=None,
    )
    nft_metadata: Optional[bool] = Field(
        description="If the result should contain the NFT metadata.",
        default=None,
    )
    order: Optional[str] = Field(
        description="The order of the result, in ascending (ASC) or descending (DESC).",
        default=DEFAULT_ORDER,
    )


class WalletHistory(PortfolioBaseTool):
    """Tool for retrieving wallet transaction history using Moralis.

    This tool uses Moralis' API to fetch the full transaction history of a specified wallet address,
    including sends, receives, token and NFT transfers, and contract interactions.
    """

    name: str = "portfolio_wallet_history"
    description: str = (
        "Retrieve the full transaction history of a specified wallet address, including sends, "
        "receives, token and NFT transfers, and contract interactions."
    )
    args_schema: Type[BaseModel] = WalletHistoryInput

    async def _arun(
        self,
        address: str,
        chain: str = DEFAULT_CHAIN,
        limit: Optional[int] = DEFAULT_LIMIT,
        cursor: Optional[str] = None,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        include_internal_transactions: Optional[bool] = None,
        nft_metadata: Optional[bool] = None,
        order: Optional[str] = DEFAULT_ORDER,
        config: RunnableConfig = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Fetch wallet transaction history from Moralis.

        Args:
            address: The wallet address to get history for
            chain: The blockchain to query
            limit: Number of results per page
            cursor: Pagination cursor
            from_block: Minimum block number
            to_block: Maximum block number
            from_date: Start date for transactions
            to_date: End date for transactions
            include_internal_transactions: Include internal txs
            nft_metadata: Include NFT metadata
            order: Order of results (ASC/DESC)
            config: The configuration for the tool call

        Returns:
            Dict containing transaction history data
        """
        context = self.context_from_config(config)
        logger.debug(
            f"wallet_history.py: Fetching wallet history with context {context}"
        )

        # Get the API key from the agent's configuration
        api_key = self.get_api_key(context)
        if not api_key:
            return {"error": "No Moralis API key provided in the configuration."}

        # Build query parameters
        params = {"chain": chain, "limit": limit, "order": order}

        # Add optional parameters if they exist
        if cursor:
            params["cursor"] = cursor
        if from_block:
            params["from_block"] = from_block
        if to_block:
            params["to_block"] = to_block
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        if include_internal_transactions is not None:
            params["include_internal_transactions"] = include_internal_transactions
        if nft_metadata is not None:
            params["nft_metadata"] = nft_metadata

        # Call Moralis API
        try:
            endpoint = f"/wallets/{address}/history"
            return await self._make_request(
                method="GET", endpoint=endpoint, api_key=api_key, params=params
            )
        except Exception as e:
            logger.error(
                f"wallet_history.py: Error fetching wallet history: {e}", exc_info=True
            )
            return {
                "error": "An error occurred while fetching wallet history. Please try again later."
            }
