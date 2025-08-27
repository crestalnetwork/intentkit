import logging
from typing import Any, Dict, Optional, Type

from langchain_core.tools import ToolException
from pydantic import BaseModel, Field
from supabase import Client, create_client

from intentkit.skills.supabase.base import SupabaseBaseTool

NAME = "supabase_fetch_data"
PROMPT = "Fetch data from a Supabase table with optional filtering, ordering, and pagination."

logger = logging.getLogger(__name__)


class SupabaseFetchDataInput(BaseModel):
    """Input for SupabaseFetchData tool."""

    table: str = Field(description="The name of the table to fetch data from")
    columns: Optional[str] = Field(
        default="*",
        description="Comma-separated list of columns to select (default: '*' for all)",
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Dictionary of filters to apply (e.g., {'column': 'value', 'age': {'gte': 18}})",
    )
    order_by: Optional[str] = Field(default=None, description="Column to order by")
    ascending: bool = Field(
        default=True, description="Whether to order in ascending order (default: True)"
    )
    limit: Optional[int] = Field(
        default=None, description="Maximum number of records to return"
    )
    offset: Optional[int] = Field(
        default=None, description="Number of records to skip for pagination"
    )


class SupabaseFetchData(SupabaseBaseTool):
    """Tool for fetching data from Supabase tables.

    This tool allows querying Supabase tables with filtering, ordering, and pagination.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: Type[BaseModel] = SupabaseFetchDataInput

    async def _arun(
        self,
        table: str,
        columns: Optional[str] = "*",
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        ascending: bool = True,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        **kwargs,
    ):
        try:
            context = self.get_context()
            supabase_url, supabase_key = self.get_supabase_config(context)

            # Create Supabase client
            supabase: Client = create_client(supabase_url, supabase_key)

            # Start building the query
            query = supabase.table(table).select(columns)

            # Apply filters if provided
            if filters:
                for column, value in filters.items():
                    if isinstance(value, dict):
                        # Handle complex filters like {'gte': 18}
                        for operator, filter_value in value.items():
                            if operator == "eq":
                                query = query.eq(column, filter_value)
                            elif operator == "neq":
                                query = query.neq(column, filter_value)
                            elif operator == "gt":
                                query = query.gt(column, filter_value)
                            elif operator == "gte":
                                query = query.gte(column, filter_value)
                            elif operator == "lt":
                                query = query.lt(column, filter_value)
                            elif operator == "lte":
                                query = query.lte(column, filter_value)
                            elif operator == "like":
                                query = query.like(column, filter_value)
                            elif operator == "ilike":
                                query = query.ilike(column, filter_value)
                            elif operator == "in":
                                query = query.in_(column, filter_value)
                            else:
                                logger.warning(f"Unknown filter operator: {operator}")
                    else:
                        # Simple equality filter
                        query = query.eq(column, value)

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
            logger.error(f"Error fetching data from Supabase: {str(e)}")
            raise ToolException(f"Failed to fetch data from table '{table}': {str(e)}")
