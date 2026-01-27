"""x402 check price skill.

This skill sends a request to a 402-protected endpoint to retrieve
the payment requirements (price information) without making a payment.
"""

import logging
from typing import Any
from urllib.parse import urlparse

import httpx
from langchain_core.tools import ArgsSchema, ToolException
from pydantic import BaseModel, Field
from x402.types import x402PaymentRequiredResponse

from intentkit.skills.x402.base import X402BaseSkill, normalize_payment_required_payload

logger = logging.getLogger(__name__)


class X402CheckPriceInput(BaseModel):
    """Arguments for checking the price of a 402-protected resource."""

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


class X402CheckPrice(X402BaseSkill):
    """Skill that checks the price of a 402-protected HTTP resource without making a payment."""

    name: str = "x402_check_price"
    description: str = (
        "Check the price of a 402-protected HTTP resource. "
        "Sends a request without payment to retrieve payment requirements. "
        "Returns the price information including amount, asset, network, and description. "
        "Use this to preview costs before making a paid request."
    )
    args_schema: ArgsSchema | None = X402CheckPriceInput

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
            elif data is not None:
                raise ToolException(
                    "POST body must be either a JSON-serializable object or a string."
                )
        elif data is not None:
            raise ToolException("Request body is only supported for POST requests.")

        try:
            # Use regular httpx client without x402 signing to get the 402 response
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(method_upper, **request_kwargs)

                if response.status_code == 402:
                    # Parse the 402 response to get payment requirements
                    try:
                        payment_data = normalize_payment_required_payload(
                            response.json()
                        )
                        payment_response = x402PaymentRequiredResponse(**payment_data)

                        # Format the payment requirements for display
                        result_parts = ["Payment Required:"]
                        for req in payment_response.accepts:
                            result_parts.append(
                                f"\n  - Amount: {req.max_amount_required}"
                            )
                            result_parts.append(f"    Asset: {req.asset}")
                            result_parts.append(f"    Network: {req.network}")
                            result_parts.append(f"    Scheme: {req.scheme}")
                            result_parts.append(f"    Pay To: {req.pay_to}")
                            result_parts.append(f"    Description: {req.description}")
                            result_parts.append(
                                f"    Max Timeout: {req.max_timeout_seconds}s"
                            )
                            if req.output_schema:
                                result_parts.append(
                                    f"    Output Schema: {req.output_schema}"
                                )
                        return "".join(result_parts)
                    except Exception as exc:
                        raise ToolException(
                            f"Failed to parse payment requirements: {exc}"
                        ) from exc
                elif response.status_code == 200:
                    return "No payment required for this resource. It is freely accessible."
                else:
                    return f"Unexpected response: HTTP {response.status_code} - {response.text}"

        except httpx.TimeoutException as exc:
            raise ToolException(
                f"Request to {url} timed out after {timeout} seconds"
            ) from exc
        except httpx.RequestError as exc:
            raise ToolException(f"Failed to connect to {url} - {str(exc)}") from exc
        except ToolException:
            raise
        except Exception as exc:
            logger.error("Unexpected error in x402_check_price", exc_info=exc)
            raise ToolException(f"Unexpected error occurred - {str(exc)}") from exc
