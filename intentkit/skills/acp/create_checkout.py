"""ACP create checkout session skill."""

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from .base import AcpBaseTool, acp_request, validate_url


class AcpCreateCheckoutInput(BaseModel):
    """Arguments for creating a checkout session."""

    merchant_url: str = Field(
        description="Base URL of the ACP merchant (e.g. https://merchant.example.com)"
    )
    items: list[dict[str, Any]] = Field(
        description='List of items to purchase. Each item: {"product_id": "prod_001", "quantity": 1}'
    )
    timeout: float = Field(default=30.0, description="Timeout in seconds.")


class AcpCreateCheckout(AcpBaseTool):
    """Create a checkout session on an ACP merchant.

    Returns session ID, payment URL, and total amount. Use x402_pay to pay
    the payment_url, then call acp_complete_checkout with the tx_hash.
    """

    name: str = "acp_create_checkout"
    description: str = (
        "Create a checkout session on an ACP merchant. "
        "Returns a session ID, payment URL, and total amount in USDC. "
        "After creating the session, use x402_pay to pay the payment_url, "
        "then call acp_complete_checkout with the tx_hash from the payment."
    )
    args_schema: ArgsSchema | None = AcpCreateCheckoutInput

    @override
    async def _arun(
        self,
        merchant_url: str,
        items: list[dict[str, Any]],
        timeout: float = 30.0,
        **_: Any,
    ) -> str:
        validate_url(merchant_url)
        url = f"{merchant_url.rstrip('/')}/checkout_sessions"
        response = await acp_request(
            "POST", url, timeout=timeout, json={"items": items}
        )

        data = response.json()
        session_id = data["id"]
        total = data["total_amount"]
        payment_url = data["payment_url"]
        price_usd = total / 1_000_000

        return (
            f"Checkout session created.\n"
            f"Session ID: {session_id}\n"
            f"Total: ${price_usd:.6f} USDC ({total} base units)\n"
            f"Payment URL: {payment_url}\n\n"
            f"Next step: Call x402_pay with method=POST, url={payment_url}, max_value={total}\n"
            f"Then call acp_complete_checkout with the tx_hash from the payment result."
        )
