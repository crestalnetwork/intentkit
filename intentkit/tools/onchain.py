"""
On-chain tool base class with unified wallet support.

This module provides the IntentKitOnChainTool class which offers
helpers for on-chain operations, supporting both CDP and Privy
wallet providers.
"""

from abc import ABCMeta
from typing import TYPE_CHECKING

from cdp import EvmServerAccount
from langchain_core.tools.base import ToolException
from web3 import AsyncWeb3

from intentkit.tools.base import IntentKitTool
from intentkit.wallets import get_agent_wallet, require_agent_wallet
from intentkit.wallets import get_cdp_network as resolve_cdp_network
from intentkit.wallets import get_evm_account as fetch_evm_account
from intentkit.wallets import get_wallet_provider as unified_get_wallet_provider
from intentkit.wallets import get_wallet_signer as unified_get_wallet_signer
from intentkit.wallets.web3 import get_async_web3_client

if TYPE_CHECKING:
    from intentkit.wallets import WalletProviderType, WalletSignerType
    from intentkit.wallets.evm_wallet import EvmWallet


class IntentKitOnChainTool(IntentKitTool, metaclass=ABCMeta):
    """
    Shared helpers for on-chain enabled tools.

    This base class provides unified access to wallet providers and signers,
    automatically selecting the appropriate implementation based on the
    provider of the agent's bound team wallet.
    """

    def web3_client(self) -> AsyncWeb3:
        """
        Get an AsyncWeb3 client for the active agent network.

        Returns:
            AsyncWeb3 instance configured for the agent's network.

        Raises:
            ValueError: If network_id is not configured.
        """
        context = self.get_context()
        agent = context.agent
        network_id = agent.network_id
        if network_id is None:
            raise ToolException("Agent network_id is not configured")
        return get_async_web3_client(network_id)

    async def get_evm_account(self) -> EvmServerAccount:
        """
        Fetch the EVM account associated with the active agent's wallet.

        Note: This method is CDP-specific. For a provider-agnostic approach,
        use get_wallet_provider() instead.

        Returns:
            The CDP EVM server account.

        Raises:
            IntentKitAPIError: If the agent's wallet is not a CDP wallet.
        """
        context = self.get_context()
        wallet = await require_agent_wallet(context.agent)
        return await fetch_evm_account(wallet)

    def get_cdp_network(self) -> str:
        """
        Get CDP network mapped from the agent's network id.

        Note: This method is CDP-specific.

        Returns:
            The CDP network identifier (e.g., 'base', 'ethereum').
        """
        context = self.get_context()
        return resolve_cdp_network(context.agent.network_id)

    # =========================================================================
    # Unified Wallet Methods (Support both CDP and Privy)
    # =========================================================================

    async def get_unified_wallet(self) -> "EvmWallet":
        """
        Get a unified wallet interface for the active agent.

        This method returns an EvmWallet instance that provides a consistent
        async interface for wallet operations, regardless of whether the
        underlying provider is CDP or Safe/Privy.

        Returns:
            An EvmWallet instance for the current agent.

        Raises:
            IntentKitAPIError: If the wallet cannot be created.

        Example:
            ```python
            wallet = await self.get_unified_wallet()
            address = wallet.address
            balance = await wallet.get_balance()
            tx_hash = await wallet.send_transaction(to="0x...", value=1000)
            ```
        """
        from intentkit.wallets.evm_wallet import EvmWallet

        context = self.get_context()
        return await EvmWallet.create(context.agent)

    async def get_wallet_provider(self) -> "WalletProviderType":
        """
        Get the wallet provider for the active agent.

        This method automatically selects the appropriate wallet provider
        based on the provider of the agent's bound team wallet:
        - 'cdp': Returns CdpWalletProvider
        - 'safe'/'privy': Returns SafeWalletProvider

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
        return provider.get_address()

    async def get_agent_wallet_provider_type(self) -> str | None:
        """
        Get the wallet provider type of the active agent's wallet.

        Returns:
            The wallet provider type ('cdp', 'native', 'readonly', 'safe',
            'privy') or None when the agent has no wallet bound.
        """
        context = self.get_context()
        wallet = await get_agent_wallet(context.agent)
        return wallet.wallet_provider if wallet else None

    async def is_onchain_capable(self) -> bool:
        """
        Check if the agent can perform on-chain operations.

        Returns:
            True if the agent's wallet supports signing
            (CDP, native, Safe, or Privy).
        """
        wallet_provider = await self.get_agent_wallet_provider_type()
        return wallet_provider in ("cdp", "native", "safe", "privy")

    def get_agent_network_id(self) -> str | None:
        """
        Get the network ID for the active agent.

        Returns:
            The network ID string (e.g., 'base-mainnet') or None if not set.
        """
        context = self.get_context()
        return context.agent.network_id
