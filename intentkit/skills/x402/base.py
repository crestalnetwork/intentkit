"""
Base class for x402 skills with unified wallet provider support.

This module provides the X402BaseSkill class which supports both
CDP and Privy wallet providers for x402 payment protocol operations.
"""

import base64
import json
import logging
from typing import Any

import httpx

from intentkit.models.x402_order import X402Order, X402OrderCreate
from intentkit.skills.onchain import IntentKitOnChainSkill

logger = logging.getLogger(__name__)

# Common HTTP status code descriptions
HTTP_STATUS_PHRASES: dict[int, str] = {
    200: "OK",
    201: "Created",
    202: "Accepted",
    204: "No Content",
    301: "Moved Permanently",
    302: "Found",
    304: "Not Modified",
    400: "Bad Request",
    401: "Unauthorized",
    402: "Payment Required",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    408: "Request Timeout",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
}

# Maximum content length to return (in bytes)
MAX_CONTENT_LENGTH = 1000


def get_status_text(status_code: int) -> str:
    """Get human-readable status text for an HTTP status code."""
    phrase = HTTP_STATUS_PHRASES.get(status_code)
    if phrase:
        return f"{status_code} {phrase}"
    # Fallback for unknown codes
    if 100 <= status_code < 200:
        return f"{status_code} Informational"
    elif 200 <= status_code < 300:
        return f"{status_code} Success"
    elif 300 <= status_code < 400:
        return f"{status_code} Redirect"
    elif 400 <= status_code < 500:
        return f"{status_code} Client Error"
    elif 500 <= status_code < 600:
        return f"{status_code} Server Error"
    return str(status_code)


def truncate_content(content: str, max_length: int = MAX_CONTENT_LENGTH) -> str:
    """Truncate content to max_length bytes, adding ellipsis if truncated."""
    content_bytes = content.encode("utf-8")
    if len(content_bytes) <= max_length:
        return content
    # Truncate and decode safely (may cut multi-byte chars)
    truncated = content_bytes[:max_length].decode("utf-8", errors="ignore")
    return truncated + "... [truncated]"


class X402BaseSkill(IntentKitOnChainSkill):
    """
    Base class for x402 skills.

    This class provides unified wallet signer support for x402 operations,
    automatically selecting the appropriate signer based on the agent's
    wallet_provider configuration (CDP or Privy).
    """

    @property
    def category(self) -> str:
        return "x402"

    async def get_signer(self) -> Any:
        """
        Get the wallet signer for x402 operations.

        This method uses the unified wallet signer interface from
        IntentKitOnChainSkill, which automatically selects:
        - ThreadSafeEvmWalletSigner for CDP wallets
        - PrivyWalletSigner for Privy wallets

        Both signers implement the required interface for x402:
        - address property
        - sign_message()
        - sign_typed_data()
        - unsafe_sign_hash()

        Returns:
            A wallet signer compatible with x402 requirements.
        """
        return await self.get_wallet_signer()

    def format_response(self, response: httpx.Response) -> str:
        """
        Format an HTTP response for skill output.

        Includes:
        - Human-readable status code
        - Chain/network and tx hash from payment response (if available)
        - Truncated content (max 1000 bytes)

        Args:
            response: The HTTP response to format

        Returns:
            Formatted response string
        """
        lines = [f"Status: {get_status_text(response.status_code)}"]

        # Extract chain and tx_hash from PAYMENT-RESPONSE header
        payment_response_header = response.headers.get("payment-response")
        if payment_response_header:
            try:
                payment_data = json.loads(base64.b64decode(payment_response_header))
                network = payment_data.get("network")
                tx_hash = payment_data.get("transaction") or payment_data.get("txHash")
                if network:
                    lines.append(f"Chain: {network}")
                if tx_hash:
                    lines.append(f"TxHash: {tx_hash}")
            except (json.JSONDecodeError, ValueError):
                pass  # Ignore parsing errors, just skip tx info

        # Truncate content if too long
        content = truncate_content(response.text)
        lines.append(f"Content: {content}")

        return "\n".join(lines)

    async def record_order(
        self,
        response: httpx.Response,
        skill_name: str,
        method: str,
        url: str,
        max_value: int | None = None,
    ) -> None:
        """
        Record an x402 order from a successful payment response.

        Extracts payment information from the PAYMENT-RESPONSE header
        and creates an order record in the database.

        Args:
            response: The HTTP response from the x402 request
            skill_name: Name of the skill that made the request
            method: HTTP method used
            url: Target URL
            max_value: Maximum payment value (for x402_pay only)
        """
        try:
            # Get context info
            context = self.get_context()
            agent_id = context.agent_id
            chat_id = context.chat_id
            user_id = context.user_id

            # Derive task_id from chat_id for autonomous tasks
            task_id = None
            if chat_id.startswith("autonomous-"):
                task_id = chat_id.removeprefix("autonomous-")

            # Parse PAYMENT-RESPONSE header (base64-encoded JSON)
            payment_response_header = response.headers.get("payment-response")
            if not payment_response_header:
                logger.debug("No PAYMENT-RESPONSE header found, skipping order record")
                return

            try:
                payment_data = json.loads(base64.b64decode(payment_response_header))
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to parse PAYMENT-RESPONSE header: {e}")
                return

            # Extract payment details
            amount = payment_data.get("amount", 0)
            asset = payment_data.get("asset", "unknown")
            network = payment_data.get("network", "unknown")
            pay_to = payment_data.get("payTo", payment_data.get("pay_to", "unknown"))
            tx_hash = payment_data.get("transaction", payment_data.get("txHash"))
            success = payment_data.get("success", True)

            # Create order record
            order = X402OrderCreate(
                agent_id=agent_id,
                chat_id=chat_id,
                user_id=user_id,
                task_id=task_id,
                skill_name=skill_name,
                method=method,
                url=url,
                max_value=max_value,
                amount=amount,
                asset=asset,
                network=network,
                pay_to=pay_to,
                tx_hash=tx_hash,
                status="success" if success else "failed",
                error=payment_data.get("errorReason"),
                http_status=response.status_code,
            )
            _ = await X402Order.create(order)
            logger.info(
                f"Recorded x402 order for agent {agent_id}: {tx_hash or 'no tx'}"
            )

        except Exception as e:
            # Don't fail the skill execution if order recording fails
            logger.error(f"Failed to record x402 order: {e}", exc_info=True)
