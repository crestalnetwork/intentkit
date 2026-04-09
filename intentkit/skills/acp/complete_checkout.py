"""ACP complete checkout session skill."""

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from .base import AcpBaseTool, acp_request, validate_url


class AcpCompleteCheckoutInput(BaseModel):
    """Arguments for completing a checkout session."""

    merchant_url: str = Field(
        description="Base URL of the ACP merchant (e.g. https://merchant.example.com)"
    )
    session_id: str = Field(description="Checkout session ID.")
    tx_hash: str = Field(
        description="Transaction hash from the x402 payment as proof of payment."
    )
    timeout: float = Field(default=30.0, description="Timeout in seconds.")


class AcpCompleteCheckout(AcpBaseTool):
    """Complete an ACP checkout session after payment.

    Call this after successfully paying via x402_pay. Provide the tx_hash
    from the payment result as proof.
    """

    name: str = "acp_complete_checkout"
    description: str = (
        "Complete an ACP checkout session after payment. "
        "Requires the session_id and tx_hash from a successful x402_pay call. "
        "The session must be in 'paid' status."
    )
    args_schema: ArgsSchema | None = AcpCompleteCheckoutInput

    @override
    async def _arun(
        self,
        merchant_url: str,
        session_id: str,
        tx_hash: str,
        timeout: float = 30.0,
        **_: Any,
    ) -> str:
        validate_url(merchant_url)
        url = f"{merchant_url.rstrip('/')}/checkout_sessions/{session_id}/complete"
        response = await acp_request(
            "POST", url, timeout=timeout, json={"tx_hash": tx_hash}
        )

        data = response.json()
        total = data.get("total_amount", 0)
        price_usd = total / 1_000_000

        return (
            f"Order completed successfully!\n"
            f"Session: {data['id']}\n"
            f"Status: {data['status']}\n"
            f"Total: ${price_usd:.6f} USDC\n"
            f"TxHash: {data.get('tx_hash', tx_hash)}"
        )
