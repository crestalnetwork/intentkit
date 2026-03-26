"""OpenSea get NFTs by account skill."""

import json
from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.opensea.base import OpenSeaBaseTool

NAME = "opensea_get_nfts_by_account"


class GetNftsByAccountInput(BaseModel):
    """Input for getting NFTs owned by an account."""

    chain: str = Field(
        description=(
            "The blockchain name "
            "(e.g., 'ethereum', 'matic', 'base', 'arbitrum', 'optimism')"
        )
    )
    address: str = Field(description="The account address to query")
    collection: str | None = Field(
        default=None,
        description="Optional collection slug to filter results",
    )
    limit: int = Field(
        default=50,
        description="Number of NFTs to return (1-200, default 50)",
        ge=1,
        le=200,
    )


class OpenSeaGetNftsByAccount(OpenSeaBaseTool):
    """Get NFTs owned by an account on a specific chain."""

    name: str = NAME
    description: str = (
        "Get NFTs owned by an account address on a specific blockchain via OpenSea. "
        "Can optionally filter by collection slug. "
        "Returns NFT metadata including name, image, and collection info."
    )
    args_schema: ArgsSchema | None = GetNftsByAccountInput

    async def _arun(
        self,
        chain: str,
        address: str,
        collection: str | None = None,
        limit: int = 50,
        **kwargs: Any,
    ) -> str:
        await self.user_rate_limit_by_category(limit=30, seconds=60)

        params: dict[str, Any] = {"limit": limit}
        if collection:
            params["collection"] = collection

        data, error = await self._get(
            f"/chain/{chain}/account/{address}/nfts",
            params=params,
        )
        if error:
            return json.dumps(error)
        return json.dumps(data)
