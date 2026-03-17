import logging
from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.portfolio.base import PortfolioBaseTool
from intentkit.skills.portfolio.constants import DEFAULT_CHAIN, DEFAULT_LIMIT

logger = logging.getLogger(__name__)


class WalletNFTsInput(BaseModel):
    """Input for wallet NFTs tool."""

    address: str = Field(description="Wallet address.")
    chain: str = Field(
        description="Chain to query.",
        default=DEFAULT_CHAIN,
    )
    format: str | None = Field(
        description="Token ID format: decimal or hex.",
        default="decimal",
    )
    limit: int | None = Field(
        description="Results per page.",
        default=DEFAULT_LIMIT,
    )
    exclude_spam: bool | None = Field(
        description="Exclude spam NFTs.",
        default=True,
    )
    token_addresses: list[str] | None = Field(
        description="Filter by NFT contract addresses.",
        default=None,
    )
    cursor: str | None = Field(
        description="Pagination cursor.",
        default=None,
    )
    normalize_metadata: bool | None = Field(
        description="Normalize metadata.",
        default=True,
    )
    media_items: bool | None = Field(
        description="Include preview media.",
        default=False,
    )
    include_prices: bool | None = Field(
        description="Include last sale prices.",
        default=False,
    )


class WalletNFTs(PortfolioBaseTool):
    """Tool for retrieving NFTs owned by a wallet using Moralis.

    This tool uses Moralis' API to fetch NFTs owned by a given address, with options
    to filter and format the results.
    """

    name: str = "portfolio_wallet_nfts"
    description: str = "Get NFTs owned by a wallet address."
    args_schema: ArgsSchema | None = WalletNFTsInput

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
        logger.debug("wallet_nfts.py: Fetching wallet NFTs with context %s", context)

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
