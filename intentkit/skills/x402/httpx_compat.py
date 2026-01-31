"""Compatibility httpx client for x402 v2 transport with signer adapter.

This module replaces legacy event-hook based handling with the x402 v2
transport flow while keeping v1 seller compatibility.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Optional

import httpx
from x402 import max_amount, x402Client
from x402.http.x402_http_client import x402HTTPClient
from x402.mechanisms.evm.exact import register_exact_evm_client
from x402.mechanisms.evm.types import DOMAIN_TYPES, TypedDataDomain, TypedDataField


class PaymentError(Exception):
    """Base class for payment-related errors."""


class MissingRequestConfigError(PaymentError):
    """Raised when request configuration is missing."""


class IntentKitEvmSignerAdapter:
    """Adapter to satisfy x402 ClientEvmSigner protocol."""

    def __init__(self, signer: Any) -> None:
        self._signer = signer

    @property
    def address(self) -> str:
        return getattr(self._signer, "address")

    def sign_typed_data(
        self,
        domain: TypedDataDomain,
        types: dict[str, list[TypedDataField]],
        primary_type: str,
        message: dict[str, Any],
    ) -> bytes:
        domain_data = {
            "name": domain.name,
            "version": domain.version,
            "chainId": domain.chain_id,
            "verifyingContract": domain.verifying_contract,
        }

        message_types: dict[str, list[dict[str, str]]] = {
            "EIP712Domain": list(DOMAIN_TYPES.get("EIP712Domain", []))
        }
        for type_name, fields in types.items():
            message_types[type_name] = [
                {"name": field.name, "type": field.type} for field in fields
            ]

        signature = self._signer.sign_typed_data(
            domain_data=domain_data,
            message_types=message_types,
            message_data=message,
            full_message=None,
        )
        return _signature_to_bytes(signature)


def _signature_to_bytes(signature: Any) -> bytes:
    if isinstance(signature, bytes):
        return signature
    if isinstance(signature, bytearray):
        return bytes(signature)
    if isinstance(signature, str):
        return bytes.fromhex(signature.removeprefix("0x"))
    if hasattr(signature, "signature"):
        return _signature_to_bytes(signature.signature)
    if hasattr(signature, "hex"):
        return bytes.fromhex(signature.hex().removeprefix("0x"))
    raise ValueError(f"Unsupported signature type: {type(signature).__name__}")


def _normalize_payment_error(exc: Exception) -> str:
    if isinstance(exc, ValueError):
        return f"Invalid payment required response: {exc}"
    return f"{type(exc).__name__}: {exc}"


def _wrap_selector(
    selector: Optional[Callable[[int, list], Any]],
    hooks: "X402HttpxCompatHooks" | None,
) -> Optional[Callable[[int, list], Any]]:
    if hooks is None:
        return selector

    def wrapped(version: int, requirements: list) -> Any:
        if not requirements:
            raise ValueError("Payment requirements list is empty.")
        selected = selector(version, requirements) if selector else requirements[0]
        hooks.last_selected_requirements = selected
        return selected

    return wrapped


class X402HttpxCompatHooks:
    """Compatibility container to expose last_paid_to."""

    def __init__(self) -> None:
        self.last_paid_to: str | None = None
        self.last_payment_required: Any | None = None
        self.last_payment_required_version: int | None = None
        self.last_payment_error: str | None = None
        self.last_selected_requirements: Any | None = None


class X402CompatTransport(httpx.AsyncBaseTransport):
    """Async transport that handles 402 responses using x402 v2 client."""

    RETRY_KEY = "_x402_is_retry"

    def __init__(
        self,
        client: x402Client,
        payment_hooks: X402HttpxCompatHooks,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = client
        self._http_client = x402HTTPClient(client)
        self._transport = transport or httpx.AsyncHTTPTransport()
        self._payment_hooks = payment_hooks

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await self._transport.handle_async_request(request)
        if response.status_code != 402:
            return response

        if request.extensions.get(self.RETRY_KEY):
            return response

        if not response.request:
            raise MissingRequestConfigError("Missing request configuration")

        try:
            await response.aread()
            body_data: Any = None
            try:
                body_data = response.json()
            except Exception:
                body_data = None

            def get_header(name: str) -> str | None:
                return response.headers.get(name)

            payment_required = self._http_client.get_payment_required_response(
                get_header, body_data
            )
            self._payment_hooks.last_payment_required = payment_required
            self._payment_hooks.last_payment_required_version = getattr(
                payment_required, "x402_version", None
            )
            payment_payload = await self._client.create_payment_payload(
                payment_required
            )

            if hasattr(payment_payload, "accepted"):
                self._payment_hooks.last_selected_requirements = (
                    payment_payload.accepted
                )
                self._payment_hooks.last_paid_to = payment_payload.accepted.pay_to
            elif self._payment_hooks.last_selected_requirements is not None:
                pay_to = getattr(
                    self._payment_hooks.last_selected_requirements, "pay_to", None
                )
                if pay_to:
                    self._payment_hooks.last_paid_to = pay_to

            payment_headers = self._http_client.encode_payment_signature_header(
                payment_payload
            )

            new_headers = dict(request.headers)
            new_headers.update(payment_headers)
            new_headers["Access-Control-Expose-Headers"] = (
                "PAYMENT-RESPONSE,X-PAYMENT-RESPONSE"
            )

            new_extensions = dict(request.extensions)
            new_extensions[self.RETRY_KEY] = True

            retry_request = httpx.Request(
                method=request.method,
                url=request.url,
                headers=new_headers,
                content=request.content,
                extensions=new_extensions,
            )

            retry_response = await self._transport.handle_async_request(retry_request)
            return retry_response
        except PaymentError:
            raise
        except Exception as exc:
            error_message = _normalize_payment_error(exc)
            self._payment_hooks.last_payment_error = error_message
            raise PaymentError(f"Failed to handle payment: {error_message}") from exc

    async def aclose(self) -> None:
        await self._transport.aclose()


def _build_x402_client(
    signer: Any,
    max_value: Optional[int] = None,
    payment_requirements_selector: Optional[Callable[[int, list], Any]] = None,
    hooks: "X402HttpxCompatHooks" | None = None,
) -> x402Client:
    wrapped_selector = _wrap_selector(payment_requirements_selector, hooks)
    client = x402Client(payment_requirements_selector=wrapped_selector)
    policies = [max_amount(max_value)] if max_value is not None else None
    adapter = IntentKitEvmSignerAdapter(signer)
    register_exact_evm_client(client, adapter, policies=policies)
    return client


def x402_compat_payment_hooks(
    account: Any,
    max_value: Optional[int] = None,
    payment_requirements_selector: Optional[Callable[[int, list], Any]] = None,
) -> tuple[dict[str, list], X402HttpxCompatHooks]:
    """Return empty hooks and a compatibility hooks container."""
    hooks = X402HttpxCompatHooks()
    _ = _build_x402_client(
        account,
        max_value=max_value,
        payment_requirements_selector=payment_requirements_selector,
        hooks=hooks,
    )
    return {"request": [], "response": []}, hooks


class X402HttpxCompatClient(httpx.AsyncClient):
    """AsyncClient with built-in x402 v2 transport and v1 compatibility."""

    def __init__(
        self,
        account: Any,
        max_value: Optional[int] = None,
        payment_requirements_selector: Optional[Callable[[int, list], Any]] = None,
        **kwargs: Any,
    ) -> None:
        payment_hooks = X402HttpxCompatHooks()
        client = _build_x402_client(
            account,
            max_value=max_value,
            payment_requirements_selector=payment_requirements_selector,
            hooks=payment_hooks,
        )
        transport = X402CompatTransport(
            client=client,
            payment_hooks=payment_hooks,
            transport=kwargs.pop("transport", None),
        )
        super().__init__(transport=transport, **kwargs)
        self.payment_hooks = payment_hooks
