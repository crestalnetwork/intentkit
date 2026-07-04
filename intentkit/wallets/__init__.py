import logging
from typing import TYPE_CHECKING, Any, TypeAlias

from intentkit.models.wallet import TeamWallet
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


async def get_agent_wallet(agent: "Agent") -> TeamWallet | None:
    """Resolve the team wallet an agent is authorized to use, if any.

    Wallets are team property: the lookup only succeeds for wallets owned by
    the agent's own team (``TeamWallet.get_for_team``).
    """
    if not agent.wallet_id:
        return None
    wallet = await TeamWallet.get_for_team(agent.wallet_id, agent.team_id)
    if wallet is None:
        logger.warning(
            "Agent %s references missing or foreign wallet %s",
            agent.id,
            agent.wallet_id,
        )
    return wallet


async def require_agent_wallet(agent: "Agent") -> TeamWallet:
    """Like :func:`get_agent_wallet`, raising when the agent has no wallet."""
    wallet = await get_agent_wallet(agent)
    if wallet is None:
        raise IntentKitAPIError(
            400,
            "NoWalletConfigured",
            "This agent is not authorized to use a wallet. "
            "Create a wallet for the team and set the agent's wallet_id.",
        )
    return wallet


async def get_agent_wallet_address(agent: "Agent") -> str | None:
    """EVM address of the agent's wallet, or None when unbound."""
    wallet = await get_agent_wallet(agent)
    return wallet.evm_wallet_address if wallet else None


def _wallet_payload(wallet: TeamWallet, error_prefix: str) -> dict[str, Any]:
    data = wallet.wallet_data_json()
    if not data:
        raise IntentKitAPIError(
            400,
            f"{error_prefix}NotInitialized",
            f"Wallet {wallet.id} has no provider data.",
        )
    return data


async def get_wallet_provider(agent: "Agent") -> WalletProviderType:
    wallet = await require_agent_wallet(agent)

    if wallet.wallet_provider == "cdp":
        return await get_cdp_wallet_provider(wallet, agent.network_id)

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


async def get_wallet_signer(agent: "Agent") -> WalletSignerType:
    wallet = await require_agent_wallet(agent)

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
    "get_agent_wallet",
    "get_agent_wallet_address",
    "get_cdp_client",
    "get_cdp_network",
    "get_evm_account",
    "get_wallet_provider",
    "get_wallet_signer",
    "require_agent_wallet",
]
