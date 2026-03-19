"""Dune run raw SQL skill."""

from decimal import Decimal
from typing import Any, override

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.dune.base import DuneBaseTool


class DuneRunSQLInput(BaseModel):
    """Input for executing raw DuneSQL."""

    sql: str = Field(description="The DuneSQL query to execute.")
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of result rows (1-1000).",
    )


class DuneRunSQL(DuneBaseTool):
    """Execute a raw DuneSQL query and return results.

    Creates a private query, executes it, polls until complete,
    then returns the formatted results.
    """

    name: str = "dune_run_sql"
    description: str = (
        "Execute a raw DuneSQL query against blockchain data. "
        "Use this for custom analytics when no saved query exists."
    )
    args_schema: ArgsSchema | None = DuneRunSQLInput
    price: Decimal = Decimal("30")

    @override
    async def _arun(
        self,
        sql: str,
        limit: int = 100,
        **kwargs: Any,
    ) -> str:
        # Create a private query
        create_resp = await self._dune_request(
            "POST",
            "/query",
            json_body={
                "name": "IntentKit ad-hoc query",
                "query_sql": sql,
                "is_private": True,
            },
        )
        query_id = create_resp.get("query_id")
        if not query_id:
            raise ToolException("Failed to create query: no query_id returned.")

        # Execute the query
        exec_resp = await self._dune_request("POST", f"/query/{query_id}/execute")
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
