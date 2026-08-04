"""Base class for ACP (Agentic Commerce Protocol) tools."""

from typing import Any

import httpx
from langchain_core.tools import ToolException

from intentkit.tools.base import IntentKitTool
from intentkit.tools.http.base import truncate_response
from intentkit.utils.ssrf import httpx_request_guard

__all__ = ["AcpBaseTool", "acp_request", "truncate_response"]


async def acp_request(
    method: str,
    url: str,
    timeout: float = 30.0,
    **kwargs: Any,
) -> httpx.Response:
    """Make an HTTP request with standard ACP error handling.

    The merchant URL is a tool argument, so the client carries the SSRF
    guard — every ACP tool is covered here rather than at each call site.

    Raises ToolException on a blocked target, timeout, HTTP or network errors.
    """
    try:
        async with httpx.AsyncClient(
            timeout=timeout, event_hooks={"request": [httpx_request_guard]}
        ) as client:
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
        raise ToolException(f"Network error: {exc!s}") from exc


class AcpBaseTool(IntentKitTool):
    """Base class for ACP tools.

    ACP tools are HTTP-based (not on-chain). Payment is handled separately
    by the x402_pay tool.
    """

    category: str = "acp"
    description: str = ""
