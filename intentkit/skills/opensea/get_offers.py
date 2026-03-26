"""OpenSea get offers skill."""

import json
from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.opensea.base import OpenSeaBaseTool

NAME = "opensea_get_offers"


class GetOffersInput(BaseModel):
    """Input for getting collection offers."""

    slug: str = Field(description="The collection slug (e.g., 'boredapeyachtclub')")
    limit: int = Field(
        default=20,
        description="Number of offers to return (1-50, default 20)",
        ge=1,
        le=50,
    )


class OpenSeaGetOffers(OpenSeaBaseTool):
    """Get offers for an NFT collection on OpenSea."""

    name: str = NAME
    description: str = (
        "Get offers for an NFT collection on OpenSea, "
        "including offer price, bidder, and expiration time."
    )
    args_schema: ArgsSchema | None = GetOffersInput

    async def _arun(self, slug: str, limit: int = 20, **kwargs: Any) -> str:
        await self.user_rate_limit_by_category(limit=30, seconds=60)

        data, error = await self._get(
            f"/offers/collection/{slug}",
            params={"limit": limit},
        )
        if error:
            return json.dumps(error)

        # Simplify offers by removing verbose protocol_data
        if isinstance(data, dict) and "offers" in data:
            for offer in data["offers"]:
                offer.pop("protocol_data", None)

        return json.dumps(data)
