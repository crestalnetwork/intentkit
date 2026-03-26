"""OpenSea get events skill."""

import json
from typing import Any

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.opensea.base import OpenSeaBaseTool

NAME = "opensea_get_events"


class GetEventsInput(BaseModel):
    """Input for getting collection events."""

    slug: str = Field(description="The collection slug (e.g., 'boredapeyachtclub')")
    event_type: str | None = Field(
        default=None,
        description=(
            "Filter by event type: 'sale', 'listing', 'offer', "
            "'transfer', 'cancel'. Leave empty for all events."
        ),
    )
    limit: int = Field(
        default=20,
        description="Number of events to return (1-50, default 20)",
        ge=1,
        le=50,
    )


class OpenSeaGetEvents(OpenSeaBaseTool):
    """Get marketplace events for an NFT collection."""

    name: str = NAME
    description: str = (
        "Get marketplace events for an NFT collection on OpenSea, "
        "including sales, listings, offers, transfers, and cancellations. "
        "Can filter by event type."
    )
    args_schema: ArgsSchema | None = GetEventsInput

    async def _arun(
        self,
        slug: str,
        event_type: str | None = None,
        limit: int = 20,
        **kwargs: Any,
    ) -> str:
        await self.user_rate_limit_by_category(limit=30, seconds=60)

        params: dict[str, Any] = {"limit": limit}
        if event_type:
            params["event_type"] = event_type

        data, error = await self._get(
            f"/events/collection/{slug}",
            params=params,
        )
        if error:
            return json.dumps(error)
        return json.dumps(data)
