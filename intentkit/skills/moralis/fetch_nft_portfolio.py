"""fetching NFT portfolio for a wallet."""

import json
import logging
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.moralis.api import fetch_nft_data, get_solana_nfts
from intentkit.skills.moralis.base import WalletBaseTool

logger = logging.getLogger(__name__)


class FetchNftPortfolioInput(BaseModel):
    """Input for FetchNftPortfolio tool."""

    address: str = Field(..., description="Wallet address")
    chain_id: Optional[int] = Field(
        None,
        description="Chain ID (if not specified, fetches from all supported chains)",
    )
    include_solana: bool = Field(
        default=False, description="Whether to include Solana NFTs"
    )
    solana_network: str = Field(
        default="mainnet", description="Solana network to use (mainnet or devnet)"
    )
    limit: Optional[int] = Field(100, description="Maximum number of NFTs to return")
    normalize_metadata: bool = Field(
        True, description="Whether to normalize metadata across different standards"
    )


class NftMetadata(BaseModel):
    """Model for NFT metadata."""

    name: Optional[str] = Field(None, description="NFT name")
    description: Optional[str] = Field(None, description="NFT description")
    image: Optional[str] = Field(None, description="NFT image URL")
    animation_url: Optional[str] = Field(None, description="NFT animation URL")
    attributes: Optional[List[Dict]] = Field(None, description="NFT attributes/traits")
    external_url: Optional[str] = Field(None, description="External URL")


class NftItem(BaseModel):
    """Model for an NFT item."""

    token_id: str = Field(..., description="NFT token ID")
    token_address: str = Field(..., description="NFT contract address")
    contract_type: Optional[str] = Field(
        None, description="NFT contract type (ERC721, ERC1155, etc.)"
    )
    name: Optional[str] = Field(None, description="NFT name")
    symbol: Optional[str] = Field(None, description="NFT symbol")
    owner_of: str = Field(..., description="Owner address")
    metadata: Optional[NftMetadata] = Field(None, description="NFT metadata")
    floor_price: Optional[float] = Field(None, description="Floor price if available")
    chain: str = Field("eth", description="Blockchain network")


class NftPortfolioOutput(BaseModel):
    """Output for FetchNftPortfolio tool."""

    address: str = Field(..., description="Wallet address")
    nfts: List[NftItem] = Field(default_factory=list, description="List of NFT items")
    total_count: int = Field(0, description="Total count of NFTs")
    chains: List[str] = Field(
        default_factory=list, description="Chains included in the response"
    )
    cursor: Optional[str] = Field(None, description="Cursor for pagination")
    error: Optional[str] = Field(None, description="Error message if any")


class FetchNftPortfolio(WalletBaseTool):
    """Tool for fetching NFT portfolio for a wallet.

    This tool retrieves detailed information about NFTs owned by a wallet address,
    including metadata, media URLs, and floor prices when available.
    """

    name: str = "moralis_fetch_nft_portfolio"
    description: str = (
        "This tool fetches NFT holdings for a wallet address.\n"
        "Provide a wallet address and optionally a chain ID to get detailed information about NFTs.\n"
        "Returns:\n"
        "- NFT collection data\n"
        "- NFT metadata and attributes\n"
        "- Media URLs if available\n"
        "- Floor prices if available\n"
        "Use this tool whenever a user asks about their NFTs or digital collectibles."
    )
    args_schema: Type[BaseModel] = FetchNftPortfolioInput

    async def _arun(
        self,
        address: str,
        chain_id: Optional[int] = None,
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
            logger.error(f"Error fetching NFT portfolio: {str(e)}")
            return NftPortfolioOutput(
                address=address, nfts=[], total_count=0, chains=[], error=str(e)
            )

    async def _fetch_evm_nfts(
        self,
        address: str,
        chain_id: int,
        limit: int,
        normalize_metadata: bool,
        result: Dict[str, Any],
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
                    logger.warning(f"Error parsing NFT metadata: {str(e)}")
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
        self, address: str, network: str, limit: int, result: Dict[str, Any]
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
                    logger.warning(f"Error parsing Solana NFT metadata: {str(e)}")
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
