"""
On-chain skill base class with unified wallet support.

This module provides the IntentKitOnChainSkill class which offers
helpers for on-chain operations, supporting both CDP and Privy
wallet providers.
"""

import inspect
from abc import ABCMeta
from typing import TYPE_CHECKING

from cdp import EvmServerAccount
from web3 import Web3

from intentkit.clients import get_cdp_network as resolve_cdp_network
from intentkit.clients import get_evm_account as fetch_evm_account
from intentkit.clients import get_wallet_provider as unified_get_wallet_provider
from intentkit.clients import get_wallet_signer as unified_get_wallet_signer
from intentkit.clients.web3 import get_web3_client
from intentkit.skills.base import IntentKitSkill

if TYPE_CHECKING:
    from intentkit.clients import WalletProviderType, WalletSignerType


class IntentKitOnChainSkill(IntentKitSkill, metaclass=ABCMeta):
    """
    Shared helpers for on-chain enabled skills.

    This base class provides unified access to wallet providers and signers,
    automatically selecting the appropriate implementation based on the
    agent's wallet_provider configuration (CDP or Privy).
    """

    def web3_client(self) -> Web3:
        """
        Get a Web3 client for the active agent network.

        Returns:
            Web3 instance configured for the agent's network.

        Raises:
            ValueError: If network_id is not configured.
        """
        context = self.get_context()
        agent = context.agent
        network_id = agent.network_id
        if network_id is None:
            raise ValueError("Agent network_id is not configured")
        return get_web3_client(network_id)

    async def get_evm_account(self) -> EvmServerAccount:
        """
        Fetch the EVM account associated with the active agent.

        Note: This method is CDP-specific. For a provider-agnostic approach,
        use get_wallet_provider() instead.

        Returns:
            The CDP EVM server account.

        Raises:
            IntentKitAPIError: If the agent is not using CDP wallet provider.
        """
        context = self.get_context()
        agent = context.agent
        return await fetch_evm_account(agent)

    def get_cdp_network(self) -> str:
        """
        Get CDP network mapped from the agent's network id.

        Note: This method is CDP-specific.

        Returns:
            The CDP network identifier (e.g., 'base', 'ethereum').
        """
        context = self.get_context()
        agent = context.agent
        return resolve_cdp_network(agent)

    # =========================================================================
    # Unified Wallet Methods (Support both CDP and Privy)
    # =========================================================================

    async def get_wallet_provider(self) -> "WalletProviderType":
        """
        Get the wallet provider for the active agent.

        This method automatically selects the appropriate wallet provider
        based on the agent's wallet_provider configuration:
        - 'cdp': Returns CdpEvmWalletProvider
        - 'privy': Returns SafeWalletProvider

        Returns:
            The wallet provider instance.

        Raises:
            IntentKitAPIError: If the wallet provider is not supported
                or not properly configured.

        Example:
            ```python
            provider = await self.get_wallet_provider()
            address = provider.get_address()  # CDP
            # or
            address = await provider.get_address()  # Privy
            ```
        """
        context = self.get_context()
        return await unified_get_wallet_provider(context.agent)

    async def get_wallet_signer(self) -> "WalletSignerType":
        """
        Get the wallet signer for the active agent.

        This method returns a signer compatible with eth_account interfaces,
        suitable for use with libraries like x402 that require signing
        capabilities.

        The signer supports:
        - sign_message(signable_message) -> SignedMessage
        - sign_typed_data(...) -> SignedMessage
        - unsafe_sign_hash(message_hash) -> SignedMessage
        - address property

        Returns:
            The wallet signer instance:
            - 'cdp': ThreadSafeEvmWalletSigner
            - 'privy': PrivyWalletSigner

        Raises:
            IntentKitAPIError: If the wallet provider is not supported
                or not properly configured.

        Example:
            ```python
            signer = await self.get_wallet_signer()
            signature = signer.sign_message(message)
            ```
        """
        context = self.get_context()
        return await unified_get_wallet_signer(context.agent)

    async def get_wallet_address(self) -> str:
        """
        Get the wallet address for the active agent.

        This is a convenience method that works with both CDP and Privy
        wallet providers.

        Returns:
            The wallet address as a checksummed hex string.

        Raises:
            IntentKitAPIError: If the wallet provider is not configured.
        """
        provider = await self.get_wallet_provider()

        # Handle both sync (CDP) and async (Privy) address getters
        address_result = provider.get_address()
        if inspect.iscoroutine(address_result):
            # It's a coroutine (Privy)
            address: str = await address_result
        else:
            address = address_result

        return address

    def get_agent_wallet_provider_type(self) -> str | None:
        """
        Get the wallet provider type for the active agent.

        Returns:
            The wallet provider type ('cdp', 'privy', 'readonly', 'none')
            or None if not set.
        """
        context = self.get_context()
        return context.agent.wallet_provider

    def is_onchain_capable(self) -> bool:
        """
        Check if the agent can perform on-chain operations.

        Returns:
            True if the agent has a wallet provider that supports
            on-chain operations (CDP or Privy).
        """
        wallet_provider = self.get_agent_wallet_provider_type()
        return wallet_provider in ("cdp", "safe", "privy")
