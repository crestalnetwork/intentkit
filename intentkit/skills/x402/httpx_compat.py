"""Compatibility httpx client for x402 v1/v2 headers.

This module provides an httpx AsyncClient wrapper that retries 402 responses
using x402 payment headers while supporting both v1 and v2 header names.
"""

from typing import Dict, List, Optional

from eth_account import Account
from httpx import AsyncClient, Request, Response
from x402.clients.base import (
    MissingRequestConfigError,
    PaymentError,
    PaymentSelectorCallable,
    x402Client,
)
from x402.types import x402PaymentRequiredResponse

from intentkit.skills.x402.base import normalize_payment_required_payload

PAYMENT_HEADER_V1 = "X-Payment"
PAYMENT_HEADER_V2 = "PAYMENT-SIGNATURE"
PAYMENT_RESPONSE_HEADER_V1 = "X-Payment-Response"
PAYMENT_RESPONSE_HEADER_V2 = "PAYMENT-RESPONSE"
EXPOSE_HEADERS_VALUE = f"{PAYMENT_RESPONSE_HEADER_V1}, {PAYMENT_RESPONSE_HEADER_V2}"


class X402HttpxCompatHooks:
    """httpx hooks that handle 402 responses using x402 payment logic."""

    def __init__(self, client: x402Client) -> None:
        self.client = client
        self._is_retry = False
        self.last_paid_to: str | None = None

    async def on_request(self, request: Request) -> None:
        """Handle request before it is sent."""
        return None

    async def on_response(self, response: Response) -> Response:
        """Handle response after it is received."""
        if response.status_code != 402:
            return response

        if self._is_retry:
            return response

        try:
            if not response.request:
                raise MissingRequestConfigError("Missing request configuration")

            await response.aread()
            data = normalize_payment_required_payload(response.json())

            payment_response = x402PaymentRequiredResponse(**data)
            selected_requirements = self.client.select_payment_requirements(
                payment_response.accepts
            )

            payment_header = self.client.create_payment_header(
                selected_requirements, payment_response.x402_version
            )

            self._is_retry = True
            request = response.request

            request.headers[PAYMENT_HEADER_V1] = payment_header
            request.headers[PAYMENT_HEADER_V2] = payment_header

            # Store pay_to for retrieval
            self.last_paid_to = selected_requirements.pay_to

            request.headers["Access-Control-Expose-Headers"] = EXPOSE_HEADERS_VALUE

            async with AsyncClient() as client:
                retry_response = await client.send(request)

                response.status_code = retry_response.status_code
                response.headers = retry_response.headers
                response._content = retry_response._content
                return response
        except PaymentError as exc:
            self._is_retry = False
            raise exc
        except Exception as exc:
            self._is_retry = False
            raise PaymentError(f"Failed to handle payment: {str(exc)}") from exc


def x402_compat_payment_hooks(
    account: Account,
    max_value: Optional[int] = None,
    payment_requirements_selector: Optional[PaymentSelectorCallable] = None,
) -> tuple[Dict[str, List], X402HttpxCompatHooks]:
    """Create httpx event hooks for x402 payment handling with v1/v2 headers."""
    client = x402Client(
        account,
        max_value=max_value,
        payment_requirements_selector=payment_requirements_selector,
    )

    hooks = X402HttpxCompatHooks(client)

    return {
        "request": [hooks.on_request],
        "response": [hooks.on_response],
    }, hooks


class X402HttpxCompatClient(AsyncClient):
    """AsyncClient with built-in x402 v1/v2 payment handling."""

    def __init__(
        self,
        account: Account,
        max_value: Optional[int] = None,
        payment_requirements_selector: Optional[PaymentSelectorCallable] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        event_hooks, payment_hooks = x402_compat_payment_hooks(
            account, max_value, payment_requirements_selector
        )
        self.event_hooks = event_hooks
        self.payment_hooks = payment_hooks
