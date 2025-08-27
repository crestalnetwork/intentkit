import logging
from typing import Any, Dict, List, Type, Union

from langchain_core.tools import ToolException
from pydantic import BaseModel, Field
from supabase import Client, create_client

from intentkit.skills.supabase.base import SupabaseBaseTool

NAME = "supabase_insert_data"
PROMPT = "Insert new data into a Supabase table."

logger = logging.getLogger(__name__)


class SupabaseInsertDataInput(BaseModel):
    """Input for SupabaseInsertData tool."""

    table: str = Field(description="The name of the table to insert data into")
    data: Union[Dict[str, Any], List[Dict[str, Any]]] = Field(
        description="The data to insert. Can be a single object or a list of objects"
    )
    returning: str = Field(
        default="*",
        description="Columns to return after insertion (default: '*' for all)",
    )


class SupabaseInsertData(SupabaseBaseTool):
    """Tool for inserting data into Supabase tables.

    This tool allows inserting single or multiple records into Supabase tables.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: Type[BaseModel] = SupabaseInsertDataInput

    async def _arun(
        self,
        table: str,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
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

            # Insert data
            response = supabase.table(table).insert(data).execute()

            return {
                "success": True,
                "data": response.data,
                "count": len(response.data) if response.data else 0,
            }

        except Exception as e:
            logger.error(f"Error inserting data into Supabase: {str(e)}")
            raise ToolException(f"Failed to insert data into table '{table}': {str(e)}")
