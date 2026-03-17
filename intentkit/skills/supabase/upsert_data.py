import logging
from typing import Any

from langchain_core.tools import ArgsSchema, ToolException
from pydantic import BaseModel, Field

from intentkit.skills.supabase.base import SupabaseBaseTool

NAME = "supabase_upsert_data"
PROMPT = "Upsert (insert or update) data in a Supabase table."

logger = logging.getLogger(__name__)


class SupabaseUpsertDataInput(BaseModel):
    """Input for SupabaseUpsertData tool."""

    table: str = Field(description="Table name")
    data: dict[str, Any] | list[dict[str, Any]] = Field(
        description="Object or list of objects to upsert"
    )
    on_conflict: str = Field(
        description="Conflict column(s), e.g. 'id' or 'email,username'"
    )
    returning: str = Field(default="*", description="Columns to return after upsert")


class SupabaseUpsertData(SupabaseBaseTool):
    """Tool for upserting data in Supabase tables.

    This tool allows inserting new records or updating existing ones based on conflict resolution.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: ArgsSchema | None = SupabaseUpsertDataInput

    async def _arun(
        self,
        table: str,
        data: dict[str, Any] | list[dict[str, Any]],
        on_conflict: str,
        returning: str = "*",
        **kwargs,
    ):
        try:
            context = self.get_context()

            # Validate table access for public mode
            self.validate_table_access(table, context)

            supabase = self.get_supabase_client(context)

            # Upsert data
            response = (
                supabase.table(table).upsert(data, on_conflict=on_conflict).execute()
            )

            return {
                "success": True,
                "data": response.data,
                "count": len(response.data) if response.data else 0,
            }

        except Exception as e:
            logger.error("Error upserting data in Supabase: %s", e)
            raise ToolException(f"Failed to upsert data in table '{table}': {str(e)}")
