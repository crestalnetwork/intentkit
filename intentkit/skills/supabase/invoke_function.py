import logging
from typing import Any

from langchain_core.tools import ArgsSchema, ToolException
from pydantic import BaseModel, Field

from intentkit.skills.supabase.base import SupabaseBaseTool

NAME = "supabase_invoke_function"
PROMPT = "Invoke a Supabase Edge Function with optional parameters."

logger = logging.getLogger(__name__)


class SupabaseInvokeFunctionInput(BaseModel):
    """Input for SupabaseInvokeFunction tool."""

    function_name: str = Field(description="Edge Function name")
    parameters: dict[str, Any] | None = Field(
        default=None, description="Parameters to pass to the function"
    )
    headers: dict[str, str] | None = Field(
        default=None, description="Additional request headers"
    )


class SupabaseInvokeFunction(SupabaseBaseTool):
    """Tool for invoking Supabase Edge Functions.

    This tool allows calling Supabase Edge Functions with optional parameters and headers.
    """

    name: str = NAME
    description: str = PROMPT
    args_schema: ArgsSchema | None = SupabaseInvokeFunctionInput

    async def _arun(
        self,
        function_name: str,
        parameters: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs,
    ):
        try:
            context = self.get_context()
            supabase = self.get_supabase_client(context)

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
                "data": response.json() if hasattr(response, "json") else response,  # pyright: ignore[reportAttributeAccessIssue]
                "status_code": getattr(response, "status_code", None),
            }

        except Exception as e:
            logger.error("Error invoking Supabase Edge Function: %s", e)
            raise ToolException(
                f"Failed to invoke Edge Function '{function_name}': {str(e)}"
            )
