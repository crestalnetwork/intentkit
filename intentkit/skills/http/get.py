import logging
from typing import Any

import httpx
from langchain_core.tools import ArgsSchema, ToolException
from pydantic import BaseModel, Field

from intentkit.skills.http.base import HttpBaseTool, truncate_response, validate_url

logger = logging.getLogger(__name__)


class HttpGetInput(BaseModel):
    """Input for HTTP GET request."""

    url: str = Field(description="Target URL.")
    headers: dict[str, str] | None = Field(
        description="Request headers.",
        default=None,
    )
    params: dict[str, Any] | None = Field(
        description="Query parameters.",
        default=None,
    )
    timeout: float | None = Field(
        description="Timeout in seconds.",
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
        "Make an HTTP GET request to a URL. Returns the response as text."
    )
    args_schema: ArgsSchema | None = HttpGetInput

    async def _arun(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
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
            validate_url(url)
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
                return f"Status: {response.status_code}\nContent: {truncate_response(response.text)}"

        except httpx.TimeoutException as exc:
            raise ToolException(
                f"Request to {url} timed out after {timeout} seconds"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ToolException(
                f"HTTP {exc.response.status_code} - {truncate_response(exc.response.text)}"
            ) from exc
        except httpx.RequestError as exc:
            raise ToolException(f"Failed to connect to {url} - {str(exc)}") from exc
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error in HTTP GET request", exc_info=exc)
            raise ToolException(f"Unexpected error occurred - {str(exc)}") from exc
