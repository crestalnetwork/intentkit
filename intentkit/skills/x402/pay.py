"""x402 pay skill.

This skill performs a paid HTTP request with a configurable maximum payment amount.
"""

import logging
from typing import Any, override
from urllib.parse import urlparse

import httpx
from langchain_core.tools import ArgsSchema, ToolException
from pydantic import BaseModel, Field

from intentkit.skills.x402.base import X402BaseSkill
from intentkit.skills.x402.httpx_compat import X402HttpxCompatClient

logger = logging.getLogger(__name__)


class X402PayInput(BaseModel):
    """Arguments for a paid x402 HTTP request with max value limit."""

    method: str = Field(description="HTTP method to use. Supported values: GET, POST.")
    url: str = Field(
        description="Absolute URL for the request (must include scheme and host)."
    )
    max_value: int = Field(
        description=(
            "Maximum allowed payment amount in base units (e.g., for USDC with 6 decimals, "
            "1000000 = 1 USDC). The request will fail if the required payment exceeds this limit."
        ),
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


class X402Pay(X402BaseSkill):
    """Skill that performs a paid HTTP request with max payment limit via x402."""

    name: str = "x402_pay"
    description: str = (
        "Send a paid HTTP GET or POST request using the x402 payment protocol "
        "with a specified maximum payment limit. "
        "You MUST specify max_value to limit the maximum payment amount in base units. "
        "For example, with USDC (6 decimals): 1000000 = 1 USDC, 100000 = 0.1 USDC. "
        "The request will automatically fail if the required payment exceeds max_value. "
        "Use x402_check_price first to know the exact cost before paying."
    )
    args_schema: ArgsSchema | None = X402PayInput

    @override
    async def _arun(
        self,
        method: str,
        url: str,
        max_value: int,
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

        if max_value <= 0:
            raise ToolException("max_value must be a positive integer.")

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
            elif data is not None:
                raise ToolException(
                    "POST body must be either a JSON-serializable object or a string."
                )
        elif data is not None:
            raise ToolException("Request body is only supported for POST requests.")

        try:
            await self._prefund_safe_wallet(
                method=method_upper,
                request_kwargs=request_kwargs,
                timeout=timeout,
                max_value=max_value,
            )
            account = await self.get_signer()
            async with X402HttpxCompatClient(
                account=account,
                max_value=max_value,
                timeout=timeout,
            ) as client:
                response = await client.request(method_upper, **request_kwargs)
                response.raise_for_status()

                # Get the address we paid to from the hooks
                pay_to = client.payment_hooks.last_paid_to

                # Record the order
                await self.record_order(
                    response=response,
                    skill_name=self.name,
                    method=method_upper,
                    url=url,
                    max_value=max_value,
                    pay_to_fallback=pay_to,
                )

                return self.format_response(response)
        except ValueError as exc:
            # x402HttpxClient raises ValueError when payment exceeds max_value
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
        except ToolException:
            raise
        except Exception as exc:
            logger.error("Unexpected error in x402_pay", exc_info=exc)
            raise ToolException(f"Unexpected error occurred - {str(exc)}") from exc
