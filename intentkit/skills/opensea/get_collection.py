"""OpenSea get collection skill."""

import json
from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.opensea.base import OpenSeaBaseTool

NAME = "opensea_get_collection"


class GetCollectionInput(BaseModel):
    """Input for getting an OpenSea collection."""

    slug: str = Field(
        description="The collection slug (e.g., 'boredapeyachtclub', 'cryptopunks')"
    )


class OpenSeaGetCollection(OpenSeaBaseTool):
    """Get detailed information about an NFT collection on OpenSea."""

    name: str = NAME
    description: str = (
        "Get detailed information about an NFT collection on OpenSea, "
        "including name, description, image, social links, and contract addresses. "
        "Use the collection slug (not the contract address)."
    )
    args_schema: ArgsSchema | None = GetCollectionInput

    async def _arun(self, slug: str, **kwargs: Any) -> str:
        await self.user_rate_limit_by_category(limit=30, seconds=60)

        data, error = await self._get(f"/collections/{slug}")
        if error:
            return json.dumps(error)
        return json.dumps(data)
