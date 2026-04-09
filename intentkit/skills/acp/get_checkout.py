"""ACP get checkout session skill."""

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from .base import AcpBaseTool, acp_request, validate_url


class AcpGetCheckoutInput(BaseModel):
    """Arguments for getting a checkout session status."""

    merchant_url: str = Field(
        description="Base URL of the ACP merchant (e.g. https://merchant.example.com)"
    )
    session_id: str = Field(description="Checkout session ID.")
    timeout: float = Field(default=30.0, description="Timeout in seconds.")


class AcpGetCheckout(AcpBaseTool):
    """Get the current status of an ACP checkout session."""

    name: str = "acp_get_checkout"
    description: str = (
        "Get the current status of an ACP checkout session. "
        "Returns session details including status, items, total, and tx_hash."
    )
    args_schema: ArgsSchema | None = AcpGetCheckoutInput

    @override
    async def _arun(
        self,
        merchant_url: str,
        session_id: str,
        timeout: float = 30.0,
        **_: Any,
    ) -> str:
        validate_url(merchant_url)
        url = f"{merchant_url.rstrip('/')}/checkout_sessions/{session_id}"
        response = await acp_request("GET", url, timeout=timeout)

        data = response.json()
        total = data.get("total_amount", 0)
        price_usd = total / 1_000_000

        lines = [
            f"Session: {data['id']}",
            f"Status: {data['status']}",
            f"Total: ${price_usd:.6f} USDC ({total} base units)",
        ]
        if data.get("tx_hash"):
            lines.append(f"TxHash: {data['tx_hash']}")

        items = data.get("items", [])
        if items:
            lines.append(f"Items: {len(items)}")
            for item in items:
                lines.append(f"  - {item['product_id']} x{item.get('quantity', 1)}")

        return "\n".join(lines)
