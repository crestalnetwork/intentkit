import logging
from typing import Any, Dict, Optional, Type

import httpx
from pydantic import BaseModel, Field

from intentkit.skills.http.base import HttpBaseTool

logger = logging.getLogger(__name__)


class HttpGetInput(BaseModel):
    """Input for HTTP GET request."""

    url: str = Field(description="The URL to send the GET request to")
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


class HttpGet(HttpBaseTool):
    """Tool for making HTTP GET requests.

    This tool allows you to make HTTP GET requests to any URL with optional
    headers and query parameters. It returns the response content as a string.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "http_get"
    description: str = (
        "Make an HTTP GET request to a specified URL. "
        "You can include custom headers and query parameters. "
        "Returns the response content as text. "
        "Use this when you need to fetch data from web APIs or websites."
    )
    args_schema: Type[BaseModel] = HttpGetInput

    async def _arun(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
        **kwargs,
    ) -> str:
        """Implementation of the HTTP GET request.

        Args:
            url: The URL to send the GET request to.
            headers: Optional headers to include in the request.
            params: Optional query parameters to include in the request.
            timeout: Request timeout in seconds.
            config: The runnable config (unused but required by interface).

        Returns:
            str: The response content as text, or error message if request fails.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url=url,
                    headers=headers,
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
            logger.error(f"Unexpected error in HTTP GET request: {e}")
            return f"Error: Unexpected error occurred - {str(e)}"
