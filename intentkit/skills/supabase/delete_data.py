import logging
from typing import Any, Dict, Type

from langchain_core.tools import ToolException
from pydantic import BaseModel, Field
from supabase import Client, create_client

from intentkit.skills.supabase.base import SupabaseBaseTool

NAME = "supabase_delete_data"
PROMPT = "Delete data from a Supabase table based on filtering conditions."

logger = logging.getLogger(__name__)


class SupabaseDeleteDataInput(BaseModel):
    """Input for SupabaseDeleteData tool."""

    table: str = Field(description="The name of the table to delete data from")
    filters: Dict[str, Any] = Field(
        description="Dictionary of filters to identify which records to delete (e.g., {'id': 123})"
    )
    returning: str = Field(
        default="*",
        description="Columns to return from deleted records (default: '*' for all)",
    )


class SupabaseDeleteData(SupabaseBaseTool):
    """Tool for deleting data from Supabase tables.

    This tool allows deleting records from Supabase tables based on filter conditions.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: Type[BaseModel] = SupabaseDeleteDataInput

    async def _arun(
        self,
        table: str,
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

            # Start building the delete query
            query = supabase.table(table).delete()

            # Apply filters to identify which records to delete
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

            # Execute the delete
            response = query.execute()

            return {
                "success": True,
                "data": response.data,
                "count": len(response.data) if response.data else 0,
            }

        except Exception as e:
            logger.error(f"Error deleting data from Supabase: {str(e)}")
            raise ToolException(f"Failed to delete data from table '{table}': {str(e)}")
