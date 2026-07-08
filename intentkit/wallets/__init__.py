import logging
from typing import TYPE_CHECKING, Any, TypeAlias

from intentkit.models.wallet import TeamWallet, wallet_owner_team
from intentkit.utils.error import IntentKitAPIError
from intentkit.wallets.cdp import (
    get_cdp_client,
    get_cdp_network,
    get_evm_account,
)
from intentkit.wallets.cdp import (
    get_wallet_provider as get_cdp_wallet_provider,
)
from intentkit.wallets.native import (
    get_wallet_provider as get_native_wallet_provider,
)
from intentkit.wallets.native import (
    get_wallet_signer as get_native_signer,
)
from intentkit.wallets.privy import (
    get_wallet_provider as get_privy_provider,
)
from intentkit.wallets.privy import (
    get_wallet_signer as get_privy_signer,
)

if TYPE_CHECKING:
    from intentkit.models.agent import Agent
    from intentkit.wallets.cdp import CdpWalletProvider
    from intentkit.wallets.native import NativeWalletProvider
    from intentkit.wallets.privy import SafeWalletProvider

logger = logging.getLogger(__name__)

WalletProviderType: TypeAlias = (
    "CdpWalletProvider | NativeWalletProvider | SafeWalletProvider"
)
WalletSignerType = (
    Any  # Can be EvmLocalAccount, NativeWalletSigner, or PrivyWalletSigner
)


async def list_agent_team_wallets(agent: "Agent") -> list[TeamWallet]:
    """All wallets owned by the agent's team (its authorized wallet pool)."""
    return await TeamWallet.list_for_team(wallet_owner_team(agent.team_id))


async def resolve_team_wallet(agent: "Agent", wallet_address: str) -> TeamWallet:
    """Resolve one of the agent's team wallets by address.

    Agents never own wallets; a tool call names the wallet it wants to use by
    address and this lookup only succeeds within the agent's own team.
    """
    wallet = await TeamWallet.get_by_address(
        wallet_owner_team(agent.team_id), wallet_address
    )
    if wallet is None:
        raise IntentKitAPIError(
            400,
            "WalletNotFound",
            f"Wallet '{wallet_address}' is not one of this team's wallets. "
            "Use one of the wallet addresses listed in the system prompt.",
        )
    return wallet


def _wallet_payload(wallet: TeamWallet, error_prefix: str) -> dict[str, Any]:
    data = wallet.wallet_data_json()
    if not data:
        raise IntentKitAPIError(
            400,
            f"{error_prefix}NotInitialized",
            f"Wallet {wallet.id} has no provider data.",
        )
    return data


async def build_wallet_provider(wallet: TeamWallet) -> WalletProviderType:
    """Build the provider for an already-resolved team wallet."""
    if wallet.wallet_provider == "cdp":
        return await get_cdp_wallet_provider(wallet)

    elif wallet.wallet_provider == "native":
        return get_native_wallet_provider(_wallet_payload(wallet, "NativeWallet"))

    elif wallet.wallet_provider in ("safe", "privy"):
        return get_privy_provider(_wallet_payload(wallet, "PrivyWallet"))

    elif wallet.wallet_provider == "readonly":
        raise IntentKitAPIError(
            400,
            "ReadonlyWalletNotSupported",
            "Readonly wallets cannot perform on-chain operations that require signing.",
        )

    else:
        raise IntentKitAPIError(
            400,
            "UnsupportedWalletProvider",
            f"Wallet provider '{wallet.wallet_provider}' is not supported for on-chain operations. "
            "Supported providers are: 'cdp', 'native', 'safe', 'privy'.",
        )


async def get_wallet_provider(
    agent: "Agent", wallet_address: str
) -> WalletProviderType:
    """Build the provider for one of the agent's team wallets."""
    wallet = await resolve_team_wallet(agent, wallet_address)
    return await build_wallet_provider(wallet)


async def get_wallet_signer(agent: "Agent", wallet_address: str) -> WalletSignerType:
    """Build the signer for one of the agent's team wallets.

    This only constructs the signer; the signing authorization check
    (own-team context + team ownership) lives in the tool layer, which has
    the caller context.
    """
    wallet = await resolve_team_wallet(agent, wallet_address)

    if wallet.wallet_provider == "cdp":
        from cdp import EvmLocalAccount

        account = await get_evm_account(wallet)
        return EvmLocalAccount(account)

    elif wallet.wallet_provider == "native":
        return get_native_signer(_wallet_payload(wallet, "NativeWallet"))

    elif wallet.wallet_provider in ("safe", "privy"):
        return get_privy_signer(_wallet_payload(wallet, "PrivyWallet"))

    elif wallet.wallet_provider == "readonly":
        raise IntentKitAPIError(
            400,
            "ReadonlyWalletNotSupported",
            "Readonly wallets cannot perform signing operations.",
        )

    else:
        raise IntentKitAPIError(
            400,
            "UnsupportedWalletProvider",
            f"Wallet provider '{wallet.wallet_provider}' is not supported for signing. "
            "Supported providers are: 'cdp', 'native', 'safe', 'privy'.",
        )


__all__ = [
    "WalletProviderType",
    "WalletSignerType",
    "build_wallet_provider",
    "get_cdp_client",
    "get_cdp_network",
    "get_evm_account",
    "get_wallet_provider",
    "get_wallet_signer",
    "list_agent_team_wallets",
    "resolve_team_wallet",
]
