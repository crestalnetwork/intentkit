import logging
from typing import Any

from pydantic import BaseModel, Field

from intentkit.skills.portfolio.base import PortfolioBaseTool
from intentkit.skills.portfolio.constants import DEFAULT_CHAIN, DEFAULT_LIMIT

logger = logging.getLogger(__name__)


class WalletNFTsInput(BaseModel):
    """Input for wallet NFTs tool."""

    address: str = Field(description="The address of the wallet to get NFTs for.")
    chain: str = Field(
        description="The chain to query (e.g., 'eth', 'base', 'polygon').",
        default=DEFAULT_CHAIN,
    )
    format: str | None = Field(
        description="The format of the token ID ('decimal' or 'hex').",
        default="decimal",
    )
    limit: int | None = Field(
        description="The desired page size of the result.",
        default=DEFAULT_LIMIT,
    )
    exclude_spam: bool | None = Field(
        description="Should spam NFTs be excluded from the result?",
        default=True,
    )
    token_addresses: list[str] | None = Field(
        description="The non-fungible token (NFT) addresses to get balances for.",
        default=None,
    )
    cursor: str | None = Field(
        description="The cursor returned in the previous response (for pagination).",
        default=None,
    )
    normalize_metadata: bool | None = Field(
        description="The option to enable metadata normalization.",
        default=True,
    )
    media_items: bool | None = Field(
        description="Should preview media data be returned?",
        default=False,
    )
    include_prices: bool | None = Field(
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
    args_schema: type[BaseModel] = WalletNFTsInput

    async def _arun(
        self,
        address: str,
        chain: str = DEFAULT_CHAIN,
        format: str | None = "decimal",
        limit: int | None = DEFAULT_LIMIT,
        exclude_spam: bool | None = True,
        token_addresses: list[str] | None = None,
        cursor: str | None = None,
        normalize_metadata: bool | None = True,
        media_items: bool | None = False,
        include_prices: bool | None = False,
        **kwargs,
    ) -> dict[str, Any]:
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
        context = self.get_context()
        logger.debug(f"wallet_nfts.py: Fetching wallet NFTs with context {context}")

        # Get the API key from the agent's configuration
        api_key = self.get_api_key()
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
