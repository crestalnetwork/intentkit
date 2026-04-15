import logging
from decimal import Decimal
from typing import Any, cast, override
from urllib.parse import urlparse

import httpx
from epyxid import XID
from langchain_core.tools import ArgsSchema, ToolException
from pydantic import BaseModel, Field
from web3.exceptions import TimeExhausted, Web3RPCError

from intentkit.skills.x402.base import X402BaseSkill, format_prefund_web3_error
from intentkit.skills.x402.httpx_compat import PaymentError, X402HttpxCompatClient
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


class X402HttpRequestInput(BaseModel):
    """Arguments for a generic x402 HTTP request."""

    method: str = Field(description="HTTP method (GET or POST).")
    url: str = Field(description="Absolute URL (must include scheme and host).")
    headers: dict[str, str] | None = Field(
        default=None,
        description="Optional request headers.",
    )
    params: dict[str, Any] | None = Field(
        default=None,
        description="Optional query parameters.",
    )
    data: dict[str, Any] | str | None = Field(
        default=None,
        description="Optional body (dict as JSON, str as raw). POST only.",
    )
    timeout: float | None = Field(
        default=30.0,
        description="Timeout in seconds.",
    )
    idempotency_key: str | None = Field(
        default=None,
        description="Optional key to prevent duplicate payments. Auto-generated if omitted.",
    )


class X402HttpRequest(X402BaseSkill):
    """Skill that performs signed HTTP requests via the x402 client."""

    name: str = "x402_http_request"
    description: str = "Send a paid HTTP request using the x402 protocol. Returns response status and body."
    price: Decimal = Decimal("1")
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
        idempotency_key: str | None = None,
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

        # Ensure idempotency key is set
        if not idempotency_key:
            idempotency_key = str(XID())

        request_headers = dict(headers or {})
        request_headers["Idempotency-Key"] = idempotency_key
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
        except (TimeExhausted, Web3RPCError) as exc:
            if isinstance(exc, Web3RPCError):
                self.alert_prefund_paymaster_gas_shortage(
                    skill_name=self.name,
                    method=method_upper,
                    url=url,
                    exc=exc,
                )
            error_message = format_prefund_web3_error(exc)
            if error_message:
                raise ToolException(error_message) from exc
            raise ToolException(str(exc)) from exc
        except IntentKitAPIError as exc:
            raise ToolException(str(exc)) from exc
        except ToolException:
            raise
        except Exception as exc:
            raise ToolException(f"Unexpected error occurred - {str(exc)}") from exc
