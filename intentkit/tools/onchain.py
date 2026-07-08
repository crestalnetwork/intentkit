"""
On-chain tool base class with unified wallet support.

This module provides the IntentKitOnChainTool class which offers helpers
for on-chain operations. Agents do not own wallets: every wallet-using tool
takes a ``wallet_address`` argument naming one of the team's wallets, and
the agent picks it from the list injected into its system prompt.

Read helpers only resolve the wallet row (or use a plain web3 client);
signing helpers additionally enforce the signing authorization rule: the
wallet must belong to the agent's own team (guaranteed by the team-scoped
lookup) AND the owning team must be running the agent (``is_own_team``) — a
guest-facing conversation can never operate the team's wallets.
"""

from abc import ABCMeta
from typing import TYPE_CHECKING

from cdp import EvmServerAccount
from langchain_core.tools.base import ToolException
from web3 import AsyncWeb3

from intentkit.models.wallet import TeamWallet
from intentkit.tools.base import IntentKitTool
from intentkit.wallets import get_cdp_network as resolve_cdp_network
from intentkit.wallets import get_evm_account as fetch_evm_account
from intentkit.wallets import get_wallet_provider as unified_get_wallet_provider
from intentkit.wallets import get_wallet_signer as unified_get_wallet_signer
from intentkit.wallets import list_agent_team_wallets, resolve_team_wallet
from intentkit.wallets.web3 import get_async_web3_client

if TYPE_CHECKING:
    from intentkit.wallets import WalletProviderType, WalletSignerType
    from intentkit.wallets.evm_wallet import EvmWallet

# Description snippet for the wallet_address tool argument; keep tool schemas
# consistent across categories.
WALLET_ADDRESS_ARG_DESCRIPTION = (
    "Address of the team wallet to use. Must be one of the wallet addresses "
    "listed in your system prompt."
)


class IntentKitOnChainTool(IntentKitTool, metaclass=ABCMeta):
    """
    Shared helpers for on-chain enabled tools.

    Wallet-using tools receive the wallet address as a tool argument and
    resolve it against the agent's team wallets. Signing acquisition is
    gated on the own-team rule (see module docstring).
    """

    # =========================================================================
    # Read helpers (no signing authorization required)
    # =========================================================================

    async def list_team_wallets(self) -> list[TeamWallet]:
        """All wallets owned by the active agent's team."""
        context = self.get_context()
        return await list_agent_team_wallets(context.agent)

    async def resolve_wallet(self, wallet_address: str) -> TeamWallet:
        """
        Resolve one of the team's wallets by address (read usage).

        Works for every provider, including readonly wallets. Raises when the
        address is not one of the agent's team wallets.
        """
        context = self.get_context()
        return await resolve_team_wallet(context.agent, wallet_address)

    async def get_network_id(self, wallet_address: str) -> str:
        """The effective network of a team wallet (e.g., 'base-mainnet').

        The network follows the wallet: its default_network_id, falling back
        to the platform default.
        """
        wallet = await self.resolve_wallet(wallet_address)
        return wallet.network

    async def web3_client(self, wallet_address: str) -> AsyncWeb3:
        """An AsyncWeb3 client for the network of a team wallet."""
        return get_async_web3_client(await self.get_network_id(wallet_address))

    async def get_cdp_network(self, wallet_address: str) -> str:
        """CDP network name mapped from a team wallet's network.

        Note: This method is CDP-specific.
        """
        return resolve_cdp_network(await self.get_network_id(wallet_address))

    # =========================================================================
    # Signing helpers (guarded)
    # =========================================================================

    def ensure_signing_allowed(self) -> None:
        """
        Enforce the signing authorization rule.

        Signing is only allowed when the agent is serving its own team
        (owner, team member, or an autonomous run of the team). Guest
        conversations can read on-chain data but can never operate the
        team's wallets.

        Raises:
            ToolException: When the owning team is not running the agent.
        """
        context = self.get_context()
        if not context.is_own_team:
            raise ToolException(
                "Signing is not allowed in this conversation: this agent is "
                "being used outside its own team, and team wallets can only "
                "be operated by the team itself."
            )

    async def get_signing_wallet(self, wallet_address: str) -> TeamWallet:
        """Resolve a team wallet for a signing operation (guarded)."""
        self.ensure_signing_allowed()
        return await self.resolve_wallet(wallet_address)

    async def get_unified_wallet(self, wallet_address: str) -> "EvmWallet":
        """
        Get a unified wallet interface for a team wallet (signing-capable).

        Returns an EvmWallet instance providing a consistent async interface
        regardless of the underlying provider.
        """
        from intentkit.wallets.evm_wallet import EvmWallet

        self.ensure_signing_allowed()
        context = self.get_context()
        return await EvmWallet.create(context.agent, wallet_address)

    async def get_wallet_provider(self, wallet_address: str) -> "WalletProviderType":
        """
        Get the provider object for a team wallet (signing-capable).

        The provider can send transactions, so acquisition is gated on the
        signing authorization rule.
        """
        self.ensure_signing_allowed()
        context = self.get_context()
        return await unified_get_wallet_provider(context.agent, wallet_address)

    async def get_wallet_signer(self, wallet_address: str) -> "WalletSignerType":
        """
        Get the signer for a team wallet (guarded).

        The signer supports sign_message / sign_typed_data /
        unsafe_sign_hash and exposes an address property.
        """
        self.ensure_signing_allowed()
        context = self.get_context()
        return await unified_get_wallet_signer(context.agent, wallet_address)

    async def get_evm_account(self, wallet_address: str) -> EvmServerAccount:
        """
        Fetch the CDP EVM account behind a team wallet (signing-capable).

        Note: CDP-specific; raises when the wallet is not a CDP wallet.
        """
        self.ensure_signing_allowed()
        wallet = await self.resolve_wallet(wallet_address)
        return await fetch_evm_account(wallet)
