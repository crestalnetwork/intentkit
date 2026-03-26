"""OpenSea get NFT skill."""

import json
from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.opensea.base import OpenSeaBaseTool

NAME = "opensea_get_nft"


class GetNftInput(BaseModel):
    """Input for getting a specific NFT."""

    chain: str = Field(
        description=(
            "The blockchain name "
            "(e.g., 'ethereum', 'matic', 'base', 'arbitrum', 'optimism')"
        )
    )
    address: str = Field(description="The NFT contract address")
    identifier: str = Field(description="The token ID of the NFT")


class OpenSeaGetNft(OpenSeaBaseTool):
    """Get detailed information about a specific NFT on OpenSea."""

    name: str = NAME
    description: str = (
        "Get detailed information about a specific NFT on OpenSea, "
        "including metadata, traits, rarity, and collection info. "
        "Requires the chain name, contract address, and token ID."
    )
    args_schema: ArgsSchema | None = GetNftInput

    async def _arun(
        self, chain: str, address: str, identifier: str, **kwargs: Any
    ) -> str:
        await self.user_rate_limit_by_category(limit=30, seconds=60)

        data, error = await self._get(
            f"/chain/{chain}/contract/{address}/nfts/{identifier}"
        )
        if error:
            return json.dumps(error)
        return json.dumps(data)
