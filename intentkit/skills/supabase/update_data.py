import logging
from typing import Any, Dict, Type

from langchain_core.tools import ToolException
from pydantic import BaseModel, Field
from supabase import Client, create_client

from intentkit.skills.supabase.base import SupabaseBaseTool

NAME = "supabase_update_data"
PROMPT = "Update existing data in a Supabase table with filtering conditions."

logger = logging.getLogger(__name__)


class SupabaseUpdateDataInput(BaseModel):
    """Input for SupabaseUpdateData tool."""

    table: str = Field(description="The name of the table to update data in")
    data: Dict[str, Any] = Field(
        description="The data to update (key-value pairs of columns and new values)"
    )
    filters: Dict[str, Any] = Field(
        description="Dictionary of filters to identify which records to update (e.g., {'id': 123})"
    )
    returning: str = Field(
        default="*", description="Columns to return after update (default: '*' for all)"
    )


class SupabaseUpdateData(SupabaseBaseTool):
    """Tool for updating data in Supabase tables.

    This tool allows updating records in Supabase tables based on filter conditions.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: Type[BaseModel] = SupabaseUpdateDataInput

    async def _arun(
        self,
        table: str,
        data: Dict[str, Any],
        filters: Dict[str, Any],
        returning: str = "*",
        **kwargs,
    ):
        try:
            context = self.get_context()

            # Validate table access for public mode
            self.validate_table_access(table, context)

            supabase_url, supabase_key = self.get_supabase_config(context)

            # Create Supabase client
            supabase: Client = create_client(supabase_url, supabase_key)

            # Start building the update query
            query = supabase.table(table).update(data)

            # Apply filters to identify which records to update
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

            # Execute the update
            response = query.execute()

            return {
                "success": True,
                "data": response.data,
                "count": len(response.data) if response.data else 0,
            }

        except Exception as e:
            logger.error(f"Error updating data in Supabase: {str(e)}")
            raise ToolException(f"Failed to update data in table '{table}': {str(e)}")
