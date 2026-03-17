"""fetching NFT portfolio for a wallet."""

import json
import logging
from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.moralis.api import fetch_nft_data, get_solana_nfts
from intentkit.skills.moralis.base import WalletBaseTool

logger = logging.getLogger(__name__)


class FetchNftPortfolioInput(BaseModel):
    """Input for FetchNftPortfolio tool."""

    address: str = Field(..., description="Wallet address.")
    chain_id: int | None = Field(None, description="Chain ID (all chains if empty).")
    include_solana: bool = Field(default=False, description="Include Solana NFTs.")
    solana_network: str = Field(
        default="mainnet", description="Solana network: mainnet or devnet."
    )
    limit: int | None = Field(100, description="Max NFTs to return.")
    normalize_metadata: bool = Field(True, description="Normalize metadata.")


class NftMetadata(BaseModel):
    """Model for NFT metadata."""

    name: str | None = Field(None, description="Name.")
    description: str | None = Field(None, description="Description.")
    image: str | None = Field(None, description="Image URL.")
    animation_url: str | None = Field(None, description="Animation URL.")
    attributes: list[dict[str, Any]] | None = Field(None, description="Traits.")
    external_url: str | None = Field(None, description="External URL.")


class NftItem(BaseModel):
    """Model for an NFT item."""

    token_id: str = Field(..., description="Token ID.")
    token_address: str = Field(..., description="Contract address.")
    contract_type: str | None = Field(None, description="Contract type.")
    name: str | None = Field(None, description="Name.")
    symbol: str | None = Field(None, description="Symbol.")
    owner_of: str = Field(..., description="Owner address.")
    metadata: NftMetadata | None = Field(None, description="Metadata.")
    floor_price: float | None = Field(None, description="Floor price.")
    chain: str = Field("eth", description="Chain.")


class NftPortfolioOutput(BaseModel):
    """Output for FetchNftPortfolio tool."""

    address: str = Field(..., description="Wallet address.")
    nfts: list[NftItem] = Field(default_factory=list, description="NFT items.")
    total_count: int = Field(0, description="Total NFTs.")
    chains: list[str] = Field(default_factory=list, description="Chains queried.")
    cursor: str | None = Field(None, description="Pagination cursor.")
    error: str | None = Field(None, description="Error message.")


class FetchNftPortfolio(WalletBaseTool):
    """Tool for fetching NFT portfolio for a wallet.

    This tool retrieves detailed information about NFTs owned by a wallet address,
    including metadata, media URLs, and floor prices when available.
    """

    name: str = "moralis_fetch_nft_portfolio"
    description: str = (
        "Fetch NFT holdings for a wallet, including metadata and floor prices."
    )
    args_schema: ArgsSchema | None = FetchNftPortfolioInput

    async def _arun(
        self,
        address: str,
        chain_id: int | None = None,
        include_solana: bool = False,
        solana_network: str = "mainnet",
        limit: int = 100,
        normalize_metadata: bool = True,
        **kwargs,
    ) -> NftPortfolioOutput:
        """Fetch NFT portfolio for a wallet.

        Args:
            address: Wallet address to fetch NFTs for
            chain_id: Chain ID to fetch NFTs for (if None, fetches from all supported chains)
            include_solana: Whether to include Solana NFTs
            solana_network: Solana network to use (mainnet or devnet)
            limit: Maximum number of NFTs to return
            normalize_metadata: Whether to normalize metadata across different standards

        Returns:
            NftPortfolioOutput containing NFT portfolio data
        """
        try:
            # Initialize result
            result = {"address": address, "nfts": [], "total_count": 0, "chains": []}

            # Fetch EVM NFTs
            if chain_id is not None:
                # Fetch from specific chain
                await self._fetch_evm_nfts(
                    address, chain_id, limit, normalize_metadata, result
                )
            else:
                # Fetch from all supported chains
                from intentkit.skills.moralis.base import CHAIN_MAPPING

                for chain_id in CHAIN_MAPPING.keys():
                    await self._fetch_evm_nfts(
                        address,
                        chain_id,
                        limit // len(CHAIN_MAPPING),
                        normalize_metadata,
                        result,
                    )

            # Fetch Solana NFTs if requested
            if include_solana:
                await self._fetch_solana_nfts(address, solana_network, limit, result)

            return NftPortfolioOutput(**result)

        except Exception as e:
            logger.error("Error fetching NFT portfolio: %s", e)
            return NftPortfolioOutput(
                address=address, nfts=[], total_count=0, chains=[], error=str(e)
            )

    async def _fetch_evm_nfts(
        self,
        address: str,
        chain_id: int,
        limit: int,
        normalize_metadata: bool,
        result: dict[str, Any],
    ) -> None:
        """Fetch NFTs from an EVM chain.

        Args:
            address: Wallet address
            chain_id: Chain ID
            limit: Maximum number of NFTs to return
            normalize_metadata: Whether to normalize metadata
            result: Result dictionary to update
        """
        params = {"limit": limit, "normalizeMetadata": normalize_metadata}

        nft_data = await fetch_nft_data(self.api_key, address, chain_id, params)

        if "error" in nft_data:
            return

        chain_name = self._get_chain_name(chain_id)
        if chain_name not in result["chains"]:
            result["chains"].append(chain_name)

        result["total_count"] += nft_data.get("total", 0)

        if "cursor" in nft_data:
            result["cursor"] = nft_data["cursor"]

        for nft in nft_data.get("result", []):
            # Extract metadata
            metadata = None
            if "metadata" in nft and nft["metadata"]:
                try:
                    if isinstance(nft["metadata"], str):
                        metadata_dict = json.loads(nft["metadata"])
                    else:
                        metadata_dict = nft["metadata"]

                    metadata = NftMetadata(
                        name=metadata_dict.get("name"),
                        description=metadata_dict.get("description"),
                        image=metadata_dict.get("image"),
                        animation_url=metadata_dict.get("animation_url"),
                        attributes=metadata_dict.get("attributes"),
                        external_url=metadata_dict.get("external_url"),
                    )
                except Exception as e:
                    logger.warning("Error parsing NFT metadata: %s", e)
                    # If metadata parsing fails, continue without it
                    pass

            # Create NFT item
            nft_item = NftItem(
                token_id=nft.get("token_id", ""),
                token_address=nft.get("token_address", ""),
                contract_type=nft.get("contract_type"),
                name=nft.get("name"),
                symbol=nft.get("symbol"),
                owner_of=nft.get("owner_of", address),
                metadata=metadata,
                floor_price=nft.get("floor_price"),
                chain=chain_name,
            )

            result["nfts"].append(nft_item)

    async def _fetch_solana_nfts(
        self, address: str, network: str, limit: int, result: dict[str, Any]
    ) -> None:
        """Fetch NFTs from Solana.

        Args:
            address: Wallet address
            network: Solana network
            limit: Maximum number of NFTs to return
            result: Result dictionary to update
        """
        chain_name = "solana"
        if chain_name not in result["chains"]:
            result["chains"].append(chain_name)

        nfts_result = await get_solana_nfts(self.api_key, address, network)

        if "error" in nfts_result:
            return

        if not isinstance(nfts_result, list):
            return

        count = min(limit, len(nfts_result))
        result["total_count"] += count

        for i, nft in enumerate(nfts_result):
            if i >= limit:
                break

            # Create NFT item
            metadata = None
            if "metadata" in nft and nft["metadata"]:
                try:
                    metadata_dict = nft["metadata"]
                    if isinstance(metadata_dict, str):
                        metadata_dict = json.loads(metadata_dict)

                    metadata = NftMetadata(
                        name=metadata_dict.get("name"),
                        description=metadata_dict.get("description"),
                        image=metadata_dict.get("image"),
                        animation_url=metadata_dict.get("animation_url"),
                        attributes=metadata_dict.get("attributes"),
                        external_url=metadata_dict.get("external_url"),
                    )
                except Exception as e:
                    logger.warning("Error parsing Solana NFT metadata: %s", e)
                    pass

            nft_item = NftItem(
                token_id=nft.get("mint", ""),  # Use mint address as token ID
                token_address=nft.get("mint", ""),  # Use mint address as token address
                name=nft.get("name"),
                symbol=nft.get("symbol"),
                owner_of=address,
                metadata=metadata,
                chain=chain_name,
            )

            result["nfts"].append(nft_item)
