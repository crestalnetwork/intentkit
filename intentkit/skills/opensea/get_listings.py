"""OpenSea get listings skill."""

import json
from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.opensea.base import OpenSeaBaseTool

NAME = "opensea_get_listings"


class GetListingsInput(BaseModel):
    """Input for getting collection listings."""

    slug: str = Field(description="The collection slug (e.g., 'boredapeyachtclub')")
    limit: int = Field(
        default=20,
        description="Number of listings to return (1-50, default 20)",
        ge=1,
        le=50,
    )


class OpenSeaGetListings(OpenSeaBaseTool):
    """Get the best (lowest price) active listings for an NFT collection."""

    name: str = NAME
    description: str = (
        "Get the best active listings for an NFT collection on OpenSea, "
        "sorted by price ascending. Returns listing price, seller, "
        "expiration time, and order hash for each listing."
    )
    args_schema: ArgsSchema | None = GetListingsInput

    async def _arun(self, slug: str, limit: int = 20, **kwargs: Any) -> str:
        await self.user_rate_limit_by_category(limit=30, seconds=60)

        data, error = await self._get(
            f"/listings/collection/{slug}/best",
            params={"limit": limit},
        )
        if error:
            return json.dumps(error)

        # Simplify listings by removing verbose protocol_data
        if isinstance(data, dict) and "listings" in data:
            for listing in data["listings"]:
                listing.pop("protocol_data", None)

        return json.dumps(data)
