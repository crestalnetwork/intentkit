import logging
from typing import Any, cast, override
from urllib.parse import urlparse

import httpx
from langchain_core.tools import ArgsSchema, ToolException
from pydantic import BaseModel, Field

from intentkit.skills.x402.base import X402BaseSkill
from intentkit.skills.x402.httpx_compat import PaymentError, X402HttpxCompatClient
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


class X402HttpRequestInput(BaseModel):
    """Arguments for a generic x402 HTTP request."""

    method: str = Field(description="HTTP method to use. Supported values: GET, POST.")
    url: str = Field(
        description="Absolute URL for the request (must include scheme and host)."
    )
    headers: dict[str, str] | None = Field(
        default=None,
        description="Optional headers to include in the request.",
    )
    params: dict[str, Any] | None = Field(
        default=None,
        description="Optional query parameters to include in the request.",
    )
    data: dict[str, Any] | str | None = Field(
        default=None,
        description=(
            "Optional request body. Dictionaries are sent as JSON; strings are sent as raw data. "
            "Only supported for POST requests."
        ),
    )
    timeout: float | None = Field(
        default=30.0,
        description="Request timeout in seconds.",
    )


class X402HttpRequest(X402BaseSkill):
    """Skill that performs signed HTTP requests via the x402 client."""

    name: str = "x402_http_request"
    description: str = (
        "Send an HTTP GET or POST request using the x402 payment protocol. "
        "Provide the method, absolute URL, optional headers, query parameters, and request body. "
        "Returns the response status and body text."
    )
    args_schema: ArgsSchema | None = X402HttpRequestInput

    @override
    async def _arun(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | str | None = None,
        timeout: float = 30.0,
        **_: Any,
    ) -> str:
        method_upper = method.upper()
        if method_upper not in {"GET", "POST"}:
            raise ToolException(
                f"Unsupported HTTP method '{method}'. Only GET and POST are allowed."
            )

        parsed = urlparse(url)
        if not (parsed.scheme and parsed.netloc):
            raise ToolException("URL must include scheme and host (absolute URL).")

        request_headers = dict(headers or {})
        request_kwargs: dict[str, Any] = {
            "url": url,
            "headers": request_headers or None,
            "params": params,
            "timeout": timeout,
        }

        if method_upper == "POST":
            if isinstance(data, dict):
                header_keys = {key.lower() for key in request_headers}
                if "content-type" not in header_keys:
                    request_headers["Content-Type"] = "application/json"
                request_kwargs["json"] = data
            elif isinstance(data, str):
                request_kwargs["content"] = data

        try:
            await self._prefund_safe_wallet(
                method=method_upper,
                request_kwargs=request_kwargs,
                timeout=timeout,
            )
            account = await self.get_signer()
            async with X402HttpxCompatClient(
                account=account,
                timeout=timeout,
            ) as client:
                http_response = cast(
                    Any, await client.request(method_upper, **request_kwargs)
                )
                _ = http_response.raise_for_status()

                # Record the order
                pay_to = client.payment_hooks.last_paid_to
                await self.record_order(
                    response=http_response,
                    skill_name=self.name,
                    method=method_upper,
                    url=url,
                    pay_to_fallback=pay_to,
                )

                return self.format_response(http_response)
        except ValueError as exc:
            raise ToolException(str(exc)) from exc
        except PaymentError as exc:
            raise ToolException(str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise ToolException(
                f"Request to {url} timed out after {timeout} seconds"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ToolException(
                f"HTTP {exc.response.status_code} - {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise ToolException(f"Failed to connect to {url} - {str(exc)}") from exc
        except IntentKitAPIError as exc:
            raise ToolException(str(exc)) from exc
        except ToolException:
            raise
        except Exception as exc:
            raise ToolException(f"Unexpected error occurred - {str(exc)}") from exc
