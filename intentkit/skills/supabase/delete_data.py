import logging
from typing import Any

from langchain_core.tools import ArgsSchema, ToolException
from pydantic import BaseModel, Field

from intentkit.skills.supabase.base import SupabaseBaseTool

NAME = "supabase_delete_data"
PROMPT = "Delete records from a Supabase table using filters."

logger = logging.getLogger(__name__)


class SupabaseDeleteDataInput(BaseModel):
    """Input for SupabaseDeleteData tool."""

    table: str = Field(description="Table name")
    filters: dict[str, Any] = Field(
        description="Filters to match records, e.g. {'id': 123}"
    )
    returning: str = Field(
        default="*",
        description="Columns to return from deleted records",
    )


class SupabaseDeleteData(SupabaseBaseTool):
    """Tool for deleting data from Supabase tables.

    This tool allows deleting records from Supabase tables based on filter conditions.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: ArgsSchema | None = SupabaseDeleteDataInput

    async def _arun(
        self,
        table: str,
        filters: dict[str, Any],
        returning: str = "*",
        **kwargs,
    ):
        try:
            context = self.get_context()

            # Validate table access for public mode
            self.validate_table_access(table, context)

            supabase = self.get_supabase_client(context)

            # Start building the delete query
            query = supabase.table(table).delete()

            # Apply filters to identify which records to delete
            query = self.apply_filters(query, filters)

            # Execute the delete
            response = query.execute()

            return {
                "success": True,
                "data": response.data,
                "count": len(response.data) if response.data else 0,
            }

        except Exception as e:
            logger.error("Error deleting data from Supabase: %s", e)
            raise ToolException(f"Failed to delete data from table '{table}': {str(e)}")
