"""
Base class for x402 skills with unified wallet provider support.

This module provides the X402BaseSkill class which supports both
CDP and Privy wallet providers for x402 payment protocol operations.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from x402.clients.httpx import x402HttpxClient

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

    async def _get_signer(self) -> Any:
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

    @asynccontextmanager
    async def http_client(
        self,
        timeout: float = 30.0,
    ) -> AsyncIterator[x402HttpxClient]:
        """
        Create an x402 HTTP client with automatic payment signing.

        This context manager creates an x402HttpxClient configured with
        the agent's wallet signer, enabling automatic payment for
        402-protected HTTP resources.

        Args:
            timeout: Request timeout in seconds.

        Yields:
            x402HttpxClient instance ready for making paid requests.

        Raises:
            Exception: If client creation fails.

        Example:
            ```python
            async with self.http_client() as client:
                response = await client.get("https://api.example.com/paid-resource")
            ```
        """
        account = await self._get_signer()
        try:
            async with x402HttpxClient(
                account=account,
                timeout=timeout,
            ) as client:
                yield client
        except Exception:
            logger.exception("Failed to create x402 HTTP client")
            raise
