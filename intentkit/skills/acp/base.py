"""Base class for ACP (Agentic Commerce Protocol) skills."""

from typing import Any

import httpx
from langchain_core.tools import ToolException

from intentkit.skills.base import IntentKitSkill
from intentkit.skills.http.base import truncate_response, validate_url

__all__ = ["AcpBaseTool", "acp_request", "truncate_response", "validate_url"]


async def acp_request(
    method: str,
    url: str,
    timeout: float = 30.0,
    **kwargs: Any,
) -> httpx.Response:
    """Make an HTTP request with standard ACP error handling.

    Raises ToolException on timeout, HTTP errors, or network errors.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
    except httpx.TimeoutException as exc:
        raise ToolException(f"Request timed out after {timeout}s") from exc
    except httpx.HTTPStatusError as exc:
        raise ToolException(
            f"HTTP {exc.response.status_code}: {exc.response.text}"
        ) from exc
    except httpx.RequestError as exc:
        raise ToolException(f"Network error: {str(exc)}") from exc


class AcpBaseTool(IntentKitSkill):
    """Base class for ACP skills.

    ACP skills are HTTP-based (not on-chain). Payment is handled separately
    by the x402_pay skill.
    """

    category: str = "acp"
    description: str = ""
