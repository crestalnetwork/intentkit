import logging
from typing import Any, Dict, Optional, Type, Union

import httpx
from pydantic import BaseModel, Field

from intentkit.skills.http.base import HttpBaseTool

logger = logging.getLogger(__name__)


class HttpPostInput(BaseModel):
    """Input for HTTP POST request."""

    url: str = Field(description="The URL to send the POST request to")
    data: Optional[Union[Dict[str, Any], str]] = Field(
        description="The data to send in the request body. Can be a dictionary (will be sent as JSON) or a string",
        default=None,
    )
    headers: Optional[Dict[str, str]] = Field(
        description="Optional headers to include in the request",
        default=None,
    )
    params: Optional[Dict[str, Any]] = Field(
        description="Optional query parameters to include in the request",
        default=None,
    )
    timeout: Optional[float] = Field(
        description="Request timeout in seconds (default: 30)",
        default=30.0,
    )


class HttpPost(HttpBaseTool):
    """Tool for making HTTP POST requests.

    This tool allows you to make HTTP POST requests to any URL with optional
    headers, query parameters, and request body data. It returns the response content as a string.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "http_post"
    description: str = (
        "Make an HTTP POST request to a specified URL. "
        "You can include custom headers, query parameters, and request body data. "
        "Data can be provided as a dictionary (sent as JSON) or as a string. "
        "Returns the response content as text. "
        "Use this when you need to send data to web APIs or submit forms."
    )
    args_schema: Type[BaseModel] = HttpPostInput

    async def _arun(
        self,
        url: str,
        data: Optional[Union[Dict[str, Any], str]] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
        **kwargs,
    ) -> str:
        """Implementation of the HTTP POST request.

        Args:
            url: The URL to send the POST request to.
            data: The data to send in the request body.
            headers: Optional headers to include in the request.
            params: Optional query parameters to include in the request.
            timeout: Request timeout in seconds.
            config: The runnable config (unused but required by interface).

        Returns:
            str: The response content as text, or error message if request fails.
        """
        try:
            # Prepare headers
            request_headers = headers or {}

            # If data is a dictionary, send as JSON
            if isinstance(data, dict):
                if "content-type" not in {k.lower() for k in request_headers.keys()}:
                    request_headers["Content-Type"] = "application/json"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url=url,
                    json=data if isinstance(data, dict) else None,
                    content=data if isinstance(data, str) else None,
                    headers=request_headers,
                    params=params,
                    timeout=timeout,
                )

                # Raise an exception for bad status codes
                response.raise_for_status()

                # Return response content
                return f"Status: {response.status_code}\nContent: {response.text}"

        except httpx.TimeoutException:
            return f"Error: Request to {url} timed out after {timeout} seconds"
        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} - {e.response.text}"
        except httpx.RequestError as e:
            return f"Error: Failed to connect to {url} - {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in HTTP POST request: {e}")
            return f"Error: Unexpected error occurred - {str(e)}"
