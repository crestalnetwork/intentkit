import logging
from typing import Any, Dict, List, Type, Union

from langchain_core.tools import ToolException
from pydantic import BaseModel, Field
from supabase import Client, create_client

from intentkit.skills.supabase.base import SupabaseBaseTool

NAME = "supabase_upsert_data"
PROMPT = (
    "Upsert (insert or update) data in a Supabase table based on conflict resolution."
)

logger = logging.getLogger(__name__)


class SupabaseUpsertDataInput(BaseModel):
    """Input for SupabaseUpsertData tool."""

    table: str = Field(description="The name of the table to upsert data into")
    data: Union[Dict[str, Any], List[Dict[str, Any]]] = Field(
        description="The data to upsert. Can be a single object or a list of objects"
    )
    on_conflict: str = Field(
        description="The column(s) to use for conflict resolution (e.g., 'id' or 'email,username')"
    )
    returning: str = Field(
        default="*", description="Columns to return after upsert (default: '*' for all)"
    )


class SupabaseUpsertData(SupabaseBaseTool):
    """Tool for upserting data in Supabase tables.

    This tool allows inserting new records or updating existing ones based on conflict resolution.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: Type[BaseModel] = SupabaseUpsertDataInput

    async def _arun(
        self,
        table: str,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        on_conflict: str,
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
            logger.error(f"Error upserting data in Supabase: {str(e)}")
            raise ToolException(f"Failed to upsert data in table '{table}': {str(e)}")
