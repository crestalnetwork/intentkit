"""Dune execute query skill."""

from decimal import Decimal
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.dune.base import DuneBaseTool


class DuneExecuteQueryInput(BaseModel):
    """Input for executing a saved Dune query."""

    query_id: int = Field(description="The Dune query ID to execute.")
    parameters: dict[str, str] | None = Field(
        default=None,
        description="Optional query parameters as key-value pairs.",
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of result rows (1-1000).",
    )


class DuneExecuteQuery(DuneBaseTool):
    """Execute a saved Dune query and return results.

    Triggers execution of a query by ID, polls until complete,
    then returns the formatted results.
    """

    name: str = "dune_execute_query"
    description: str = (
        "Execute a saved Dune Analytics query by ID and return fresh results. "
        "Use this when you need up-to-date blockchain data from a known query."
    )
    args_schema: ArgsSchema | None = DuneExecuteQueryInput
    price: Decimal = Decimal("20")

    @override
    async def _arun(
        self,
        query_id: int,
        parameters: dict[str, str] | None = None,
        limit: int = 100,
        **kwargs: Any,
    ) -> str:
        # Build execution payload
        body: dict[str, Any] = {}
        if parameters:
            body["query_parameters"] = [
                {"key": k, "value": v, "type": "text"} for k, v in parameters.items()
            ]

        # Execute the query
        exec_resp = await self._dune_request(
            "POST", f"/query/{query_id}/execute", json_body=body or None
        )
        execution_id = exec_resp.get("execution_id")
        if not execution_id:
            raise ToolException(
                f"Failed to execute query {query_id}: no execution_id returned."
            )

        # Poll until complete
        await self._poll_execution(execution_id)

        # Fetch results
        results = await self._get_results(execution_id, limit)
        return self._format_results(results, query_id)
