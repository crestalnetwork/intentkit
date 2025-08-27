import logging
from typing import Any, Dict, Optional, Type

from langchain_core.tools import ToolException
from pydantic import BaseModel, Field
from supabase import Client, create_client

from intentkit.skills.supabase.base import SupabaseBaseTool

NAME = "supabase_invoke_function"
PROMPT = "Invoke a Supabase Edge Function with optional parameters."

logger = logging.getLogger(__name__)


class SupabaseInvokeFunctionInput(BaseModel):
    """Input for SupabaseInvokeFunction tool."""

    function_name: str = Field(description="The name of the Edge Function to invoke")
    parameters: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional parameters to pass to the function"
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None, description="Optional headers to include in the request"
    )


class SupabaseInvokeFunction(SupabaseBaseTool):
    """Tool for invoking Supabase Edge Functions.

    This tool allows calling Supabase Edge Functions with optional parameters and headers.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: Type[BaseModel] = SupabaseInvokeFunctionInput

    async def _arun(
        self,
        function_name: str,
        parameters: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        try:
            context = self.get_context()
            supabase_url, supabase_key = self.get_supabase_config(context)

            # Create Supabase client
            supabase: Client = create_client(supabase_url, supabase_key)

            # Prepare function invocation parameters
            invoke_options = {}
            if parameters:
                invoke_options["json"] = parameters
            if headers:
                invoke_options["headers"] = headers

            # Invoke the Edge Function
            response = supabase.functions.invoke(function_name, invoke_options)

            return {
                "success": True,
                "data": response.json() if hasattr(response, "json") else response,
                "status_code": getattr(response, "status_code", None),
            }

        except Exception as e:
            logger.error(f"Error invoking Supabase Edge Function: {str(e)}")
            raise ToolException(
                f"Failed to invoke Edge Function '{function_name}': {str(e)}"
            )
