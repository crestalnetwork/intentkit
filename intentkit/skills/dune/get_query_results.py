"""Dune get cached query results skill."""

from decimal import Decimal
from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.dune.base import DuneBaseTool


class DuneGetQueryResultsInput(BaseModel):
    """Input for fetching cached Dune query results."""

    query_id: int = Field(description="The Dune query ID to fetch results for.")
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of result rows (1-1000).",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of rows to skip for pagination.",
    )


class DuneGetQueryResults(DuneBaseTool):
    """Get cached results for a Dune query without re-executing it.

    Returns the most recent cached results for a query, which is
    faster and cheaper than executing the query again.
    """

    name: str = "dune_get_query_results"
    description: str = (
        "Get cached results for a Dune Analytics query without executing it. "
        "Use this when recent results are acceptable and you don't need fresh data."
    )
    args_schema: ArgsSchema | None = DuneGetQueryResultsInput
    price: Decimal = Decimal("5")

    @override
    async def _arun(
        self,
        query_id: int,
        limit: int = 100,
        offset: int = 0,
        **kwargs: Any,
    ) -> str:
        results = await self._dune_request(
            "GET",
            f"/query/{query_id}/results",
            params={"limit": limit, "offset": offset},
        )
        return self.format_results(results, query_id)
