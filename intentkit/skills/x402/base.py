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
