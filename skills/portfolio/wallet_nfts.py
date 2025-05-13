import logging
from typing import Any, Dict, List, Optional, Type

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from skills.portfolio.base import PortfolioBaseTool
from skills.portfolio.constants import DEFAULT_CHAIN, DEFAULT_LIMIT

logger = logging.getLogger(__name__)


class WalletNFTsInput(BaseModel):
    """Input for wallet NFTs tool."""

    address: str = Field(description="The address of the wallet to get NFTs for.")
    chain: str = Field(
        description="The chain to query (e.g., 'eth', 'base', 'polygon').",
        default=DEFAULT_CHAIN,
    )
    format: Optional[str] = Field(
        description="The format of the token ID ('decimal' or 'hex').",
        default="decimal",
    )
    limit: Optional[int] = Field(
        description="The desired page size of the result.",
        default=DEFAULT_LIMIT,
    )
    exclude_spam: Optional[bool] = Field(
        description="Should spam NFTs be excluded from the result?",
        default=True,
    )
    token_addresses: Optional[List[str]] = Field(
        description="The non-fungible token (NFT) addresses to get balances for.",
        default=None,
    )
    cursor: Optional[str] = Field(
        description="The cursor returned in the previous response (for pagination).",
        default=None,
    )
    normalize_metadata: Optional[bool] = Field(
        description="The option to enable metadata normalization.",
        default=True,
    )
    media_items: Optional[bool] = Field(
        description="Should preview media data be returned?",
        default=False,
    )
    include_prices: Optional[bool] = Field(
        description="Should NFT last sale prices be included in the result?",
        default=False,
    )


class WalletNFTs(PortfolioBaseTool):
    """Tool for retrieving NFTs owned by a wallet using Moralis.

    This tool uses Moralis' API to fetch NFTs owned by a given address, with options
    to filter and format the results.
    """

    name: str = "portfolio_wallet_nfts"
    description: str = (
        "Get NFTs owned by a given wallet address. Results include token details, "
        "metadata, collection information, and optionally prices."
    )
    args_schema: Type[BaseModel] = WalletNFTsInput

    async def _arun(
        self,
        address: str,
        chain: str = DEFAULT_CHAIN,
        format: Optional[str] = "decimal",
        limit: Optional[int] = DEFAULT_LIMIT,
        exclude_spam: Optional[bool] = True,
        token_addresses: Optional[List[str]] = None,
        cursor: Optional[str] = None,
        normalize_metadata: Optional[bool] = True,
        media_items: Optional[bool] = False,
        include_prices: Optional[bool] = False,
        config: RunnableConfig = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Fetch NFTs owned by a wallet from Moralis.

        Args:
            address: The wallet address
            chain: The blockchain to query
            format: The format of the token ID ('decimal' or 'hex')
            limit: Number of results per page
            exclude_spam: Whether to exclude spam NFTs
            token_addresses: Specific NFT contracts to filter by
            cursor: Pagination cursor
            normalize_metadata: Enable metadata normalization
            media_items: Include preview media data
            include_prices: Include NFT last sale prices
            config: The configuration for the tool call

        Returns:
            Dict containing wallet NFTs data
        """
        context = self.context_from_config(config)
        logger.debug(f"wallet_nfts.py: Fetching wallet NFTs with context {context}")

        # Get the API key from the agent's configuration
        api_key = context.config.get("api_key")
        if not api_key:
            return {"error": "No Moralis API key provided in the configuration."}

        # Build query parameters
        params = {
            "chain": chain,
            "format": format,
            "limit": limit,
            "exclude_spam": exclude_spam,
            "normalizeMetadata": normalize_metadata,
            "media_items": media_items,
            "include_prices": include_prices,
        }

        # Add optional parameters if they exist
        if token_addresses:
            params["token_addresses"] = token_addresses
        if cursor:
            params["cursor"] = cursor

        # Call Moralis API
        try:
            endpoint = f"/{address}/nft"
            return await self._make_request(
                method="GET", endpoint=endpoint, api_key=api_key, params=params
            )
        except Exception as e:
            logger.error(
                f"wallet_nfts.py: Error fetching wallet NFTs: {e}", exc_info=True
            )
            return {
                "error": "An error occurred while fetching wallet NFTs. Please try again later."
            }
