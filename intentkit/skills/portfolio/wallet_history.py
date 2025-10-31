import logging
from typing import Any

from langchain_core.tools import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.portfolio.base import PortfolioBaseTool
from intentkit.skills.portfolio.constants import (
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
    limit: int | None = Field(
        description="The desired page size of the result.",
        default=DEFAULT_LIMIT,
    )
    cursor: str | None = Field(
        description="The cursor returned in the previous response (for pagination).",
        default=None,
    )
    from_block: int | None = Field(
        description="The minimum block number to get transactions from.",
        default=None,
    )
    to_block: int | None = Field(
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
    include_internal_transactions: bool | None = Field(
        description="If the result should contain the internal transactions.",
        default=None,
    )
    nft_metadata: bool | None = Field(
        description="If the result should contain the NFT metadata.",
        default=None,
    )
    order: str | None = Field(
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
    args_schema: type[BaseModel] = WalletHistoryInput

    async def _arun(
        self,
        address: str,
        chain: str = DEFAULT_CHAIN,
        limit: int | None = DEFAULT_LIMIT,
        cursor: str | None = None,
        from_block: int | None = None,
        to_block: int | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        include_internal_transactions: bool | None = None,
        nft_metadata: bool | None = None,
        order: str | None = DEFAULT_ORDER,
        **kwargs,
    ) -> dict[str, Any]:
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
        context = self.get_context()
        logger.debug(
            f"wallet_history.py: Fetching wallet history with context {context}"
        )

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
        api_key = self.get_api_key()

        try:
            endpoint = f"/wallets/{address}/history"
            return await self._make_request(
                method="GET", endpoint=endpoint, api_key=api_key, params=params
            )
        except ToolException:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "wallet_history.py: Error fetching wallet history", exc_info=exc
            )
            raise ToolException(
                "An unexpected error occurred while fetching wallet history."
            ) from exc
