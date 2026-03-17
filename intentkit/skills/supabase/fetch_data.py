import logging
from typing import Any

from langchain_core.tools import ArgsSchema, ToolException
from pydantic import BaseModel, Field

from intentkit.skills.supabase.base import SupabaseBaseTool

NAME = "supabase_fetch_data"
PROMPT = "Fetch data from a Supabase table with filtering, ordering, and pagination."

logger = logging.getLogger(__name__)


class SupabaseFetchDataInput(BaseModel):
    """Input for SupabaseFetchData tool."""

    table: str = Field(description="Table name")
    columns: str | None = Field(
        default="*",
        description="Columns to select, comma-separated",
    )
    filters: dict[str, Any] | None = Field(
        default=None,
        description="Filters, e.g. {'column': 'value', 'age': {'gte': 18}}",
    )
    order_by: str | None = Field(default=None, description="Column to order by")
    ascending: bool = Field(default=True, description="Ascending order if true")
    limit: int | None = Field(default=None, description="Max records to return")
    offset: int | None = Field(
        default=None, description="Records to skip for pagination"
    )


class SupabaseFetchData(SupabaseBaseTool):
    """Tool for fetching data from Supabase tables.

    This tool allows querying Supabase tables with filtering, ordering, and pagination.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: ArgsSchema | None = SupabaseFetchDataInput

    async def _arun(
        self,
        table: str,
        columns: str | None = "*",
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        ascending: bool = True,
        limit: int | None = None,
        offset: int | None = None,
        **kwargs,
    ):
        try:
            context = self.get_context()
            supabase = self.get_supabase_client(context)

            # Start building the query
            query = supabase.table(table).select(columns)

            # Apply filters if provided
            if filters:
                query = self.apply_filters(query, filters)

            # Apply ordering if provided
            if order_by:
                query = query.order(order_by, desc=not ascending)

            # Apply pagination
            if limit:
                query = query.limit(limit)
            if offset:
                query = query.offset(offset)

            # Execute the query
            response = query.execute()

            return {"success": True, "data": response.data, "count": len(response.data)}

        except Exception as e:
            logger.error("Error fetching data from Supabase: %s", e)
            raise ToolException(f"Failed to fetch data from table '{table}': {str(e)}")
