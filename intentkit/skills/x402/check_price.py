"""x402 check price skill.

This skill sends a request to a 402-protected endpoint to retrieve
the payment requirements (price information) without making a payment.
"""

import json
import logging
from typing import Any
from urllib.parse import urlparse

import httpx
from langchain_core.tools import ArgsSchema, ToolException
from pydantic import BaseModel, Field
from x402.schemas import PaymentRequired, PaymentRequiredV1

from intentkit.skills.x402.base import (
    X402BaseSkill,
    decode_payment_required_header,
    get_payment_required_header,
    normalize_payment_required_payload,
)

logger = logging.getLogger(__name__)


def _format_amount(requirement: Any) -> str:
    amount_value = getattr(requirement, "amount", None)
    if amount_value is None:
        amount_value = getattr(requirement, "max_amount_required", None)
    if amount_value is None:
        return "unknown"
    return str(amount_value)


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
                        payment_required_header = get_payment_required_header(response)
                        if payment_required_header:
                            payment_data = decode_payment_required_header(
                                payment_required_header
                            )
                            if not payment_data:
                                raise ToolException(
                                    "Failed to decode payment required header."
                                )
                            default_version = 2
                        else:
                            payment_data = response.json()
                            default_version = 1

                        # Debug: log full 402 response for schema inspection
                        logger.debug(
                            "Received 402 Payment Required response",
                            extra={
                                "url": url,
                                "status": response.status_code,
                                "headers": dict(response.headers),
                                "body": payment_data,
                            },
                        )

                        normalized = normalize_payment_required_payload(
                            payment_data, default_version=default_version
                        )
                        version = normalized.get("x402Version") or normalized.get(
                            "x402_version"
                        )
                        if version == 1:
                            payment_response = PaymentRequiredV1.model_validate(
                                normalized
                            )
                        else:
                            payment_response = PaymentRequired.model_validate(
                                normalized
                            )

                        # Format the payment requirements for display
                        result_parts = ["Payment Required:"]
                        resource = getattr(payment_response, "resource", None)
                        resource_description = (
                            resource.description if resource else None
                        )

                        extensions = getattr(payment_response, "extensions", None)
                        if extensions and isinstance(extensions, dict):
                            bazaar = extensions.get("bazaar")
                            if bazaar and isinstance(bazaar, dict):
                                info = bazaar.get("info")
                                schema = bazaar.get("schema")
                                if info and isinstance(info, dict):
                                    input_example = info.get("input")
                                    output_example = info.get("output")
                                    if input_example is not None:
                                        result_parts.append(
                                            f"\n  Bazaar Input Example: {json.dumps(input_example, indent=2)}"
                                        )
                                    if output_example is not None:
                                        result_parts.append(
                                            f"\n  Bazaar Output Example: {json.dumps(output_example, indent=2)}"
                                        )
                                if schema is not None:
                                    result_parts.append(
                                        f"\n  Bazaar Schema: {json.dumps(schema, indent=2)}"
                                    )

                        for req in payment_response.accepts:
                            amount = _format_amount(req)
                            result_parts.append(f"\n  - Amount: {amount}")
                            result_parts.append(
                                f"    Asset: {getattr(req, 'asset', None)}"
                            )
                            result_parts.append(
                                f"    Network: {getattr(req, 'network', None)}"
                            )
                            result_parts.append(
                                f"    Scheme: {getattr(req, 'scheme', None)}"
                            )
                            pay_to = getattr(req, "pay_to", None) or getattr(
                                req, "payTo", None
                            )
                            result_parts.append(f"    Pay To: {pay_to}")
                            description = (
                                getattr(req, "description", None)
                                or resource_description
                            )
                            result_parts.append(f"    Description: {description}")
                            result_parts.append(
                                f"    Max Timeout: {getattr(req, 'max_timeout_seconds', None)}s"
                            )

                            # Extract input schema from extra field (x402 v2)
                            extra = getattr(req, "extra", None)
                            if extra and isinstance(extra, dict):
                                input_schema = extra.get("input_schema") or extra.get(
                                    "inputSchema"
                                )
                                if input_schema:
                                    result_parts.append(
                                        f"\n    Input Schema: {json.dumps(input_schema, indent=6)}"
                                    )

                            output_schema = getattr(req, "output_schema", None)
                            if output_schema:
                                result_parts.append(
                                    f"    Output Schema: {output_schema}"
                                )
                        return "".join(result_parts)
                    except ToolException:
                        raise
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
