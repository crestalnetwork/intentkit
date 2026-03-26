"""OpenSea get collection stats skill."""

import json
from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.opensea.base import OpenSeaBaseTool

NAME = "opensea_get_collection_stats"


class GetCollectionStatsInput(BaseModel):
    """Input for getting collection statistics."""

    slug: str = Field(description="The collection slug (e.g., 'boredapeyachtclub')")


class OpenSeaGetCollectionStats(OpenSeaBaseTool):
    """Get statistics for an NFT collection including floor price and volume."""

    name: str = NAME
    description: str = (
        "Get statistics for an NFT collection on OpenSea, "
        "including floor price, total volume, total supply, "
        "number of owners, and average price."
    )
    args_schema: ArgsSchema | None = GetCollectionStatsInput

    async def _arun(self, slug: str, **kwargs: Any) -> str:
        await self.user_rate_limit_by_category(limit=30, seconds=60)

        data, error = await self._get(f"/collections/{slug}/stats")
        if error:
            return json.dumps(error)
        return json.dumps(data)
