"""
Base class for x402 skills with unified wallet provider support.

This module provides the X402BaseSkill class which supports both
CDP and Privy wallet providers for x402 payment protocol operations.
"""

from typing import Any

from intentkit.skills.onchain import IntentKitOnChainSkill


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
