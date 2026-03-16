import logging
from typing import Any

from langchain_core.tools import ArgsSchema, ToolException
from pydantic import BaseModel, Field

from intentkit.skills.supabase.base import SupabaseBaseTool

NAME = "supabase_update_data"
PROMPT = "Update records in a Supabase table using filters."

logger = logging.getLogger(__name__)


class SupabaseUpdateDataInput(BaseModel):
    """Input for SupabaseUpdateData tool."""

    table: str = Field(description="Table name")
    data: dict[str, Any] = Field(description="Column-value pairs to update")
    filters: dict[str, Any] = Field(
        description="Filters to match records, e.g. {'id': 123}"
    )
    returning: str = Field(default="*", description="Columns to return after update")


class SupabaseUpdateData(SupabaseBaseTool):
    """Tool for updating data in Supabase tables.

    This tool allows updating records in Supabase tables based on filter conditions.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: ArgsSchema | None = SupabaseUpdateDataInput

    async def _arun(
        self,
        table: str,
        data: dict[str, Any],
        filters: dict[str, Any],
        returning: str = "*",
        **kwargs,
    ):
        try:
            context = self.get_context()

            # Validate table access for public mode
            self.validate_table_access(table, context)

            supabase = self.get_supabase_client(context)

            # Start building the update query
            query = supabase.table(table).update(data)

            # Apply filters to identify which records to update
            query = self.apply_filters(query, filters)

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
