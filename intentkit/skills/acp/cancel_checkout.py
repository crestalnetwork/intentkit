"""ACP cancel checkout session skill."""

from typing import Any, override

from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from .base import AcpBaseTool, acp_request, validate_url


class AcpCancelCheckoutInput(BaseModel):
    """Arguments for cancelling a checkout session."""

    merchant_url: str = Field(
        description="Base URL of the ACP merchant (e.g. https://merchant.example.com)"
    )
    session_id: str = Field(description="Checkout session ID to cancel.")
    timeout: float = Field(default=30.0, description="Timeout in seconds.")


class AcpCancelCheckout(AcpBaseTool):
    """Cancel an ACP checkout session.

    Only sessions in 'created' status (not yet paid) can be cancelled.
    """

    name: str = "acp_cancel_checkout"
    description: str = (
        "Cancel an ACP checkout session. "
        "Only works for sessions that have not yet been paid."
    )
    args_schema: ArgsSchema | None = AcpCancelCheckoutInput

    @override
    async def _arun(
        self,
        merchant_url: str,
        session_id: str,
        timeout: float = 30.0,
        **_: Any,
    ) -> str:
        validate_url(merchant_url)
        url = f"{merchant_url.rstrip('/')}/checkout_sessions/{session_id}/cancel"
        response = await acp_request("POST", url, timeout=timeout)

        data = response.json()
        return f"Session {data['id']} cancelled. Status: {data['status']}"
