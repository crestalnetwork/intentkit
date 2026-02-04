import json
import logging
from typing import TYPE_CHECKING, Any, Union

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

WalletProviderType = Union[
    "CdpWalletProvider", "NativeWalletProvider", "SafeWalletProvider"
]
WalletSignerType = (
    Any  # Can be EvmLocalAccount, NativeWalletSigner, or PrivyWalletSigner
)


async def _get_agent_wallet_data(agent: "Agent", wallet_type: str) -> dict[str, Any]:
    from intentkit.models.agent_data import AgentData

    agent_data = await AgentData.get(agent.id)
    if wallet_type == "native":
        data_field = agent_data.native_wallet_data
        not_initialized_error = "NativeWalletNotInitialized"
        corrupted_error = "NativeWalletDataCorrupted"
        data_label = "native wallet data"
    else:
        data_field = agent_data.privy_wallet_data
        not_initialized_error = "PrivyWalletNotInitialized"
        corrupted_error = "PrivyWalletDataCorrupted"
        data_label = "wallet data"

    if not data_field:
        raise IntentKitAPIError(
            400,
            not_initialized_error,
            "Wallet has not been initialized for this agent. "
            f"Please ensure the agent was created with wallet_provider='{agent.wallet_provider}'.",
        )

    try:
        return json.loads(data_field)
    except json.JSONDecodeError as e:
        raise IntentKitAPIError(
            500,
            corrupted_error,
            f"Failed to parse {data_label}: {e}",
        ) from e


async def get_wallet_provider(agent: "Agent") -> WalletProviderType:
    if agent.wallet_provider == "cdp":
        return await get_cdp_wallet_provider(agent)

    elif agent.wallet_provider == "native":
        native_data = await _get_agent_wallet_data(agent, "native")
        return get_native_wallet_provider(native_data)

    elif agent.wallet_provider in ("safe", "privy"):
        privy_data = await _get_agent_wallet_data(agent, "privy")
        return get_privy_provider(privy_data)

    elif agent.wallet_provider == "readonly":
        raise IntentKitAPIError(
            400,
            "ReadonlyWalletNotSupported",
            "Readonly wallets cannot perform on-chain operations that require signing.",
        )

    elif agent.wallet_provider == "none" or agent.wallet_provider is None:
        raise IntentKitAPIError(
            400,
            "NoWalletConfigured",
            "This agent does not have a wallet configured. "
            "Please set wallet_provider to 'cdp', 'native', 'safe', or 'privy' in the agent configuration.",
        )

    else:
        raise IntentKitAPIError(
            400,
            "UnsupportedWalletProvider",
            f"Wallet provider '{agent.wallet_provider}' is not supported for on-chain operations. "
            "Supported providers are: 'cdp', 'native', 'safe', 'privy'.",
        )


async def get_wallet_signer(agent: "Agent") -> WalletSignerType:
    if agent.wallet_provider == "cdp":
        from cdp import EvmLocalAccount

        account = await get_evm_account(agent)
        return EvmLocalAccount(account)

    elif agent.wallet_provider == "native":
        native_data = await _get_agent_wallet_data(agent, "native")
        return get_native_signer(native_data)

    elif agent.wallet_provider in ("safe", "privy"):
        privy_data = await _get_agent_wallet_data(agent, "privy")
        return get_privy_signer(privy_data)

    elif agent.wallet_provider == "readonly":
        raise IntentKitAPIError(
            400,
            "ReadonlyWalletNotSupported",
            "Readonly wallets cannot perform signing operations.",
        )

    elif agent.wallet_provider == "none" or agent.wallet_provider is None:
        raise IntentKitAPIError(
            400,
            "NoWalletConfigured",
            "This agent does not have a wallet configured. "
            "Please set wallet_provider to 'cdp', 'native', 'safe', or 'privy' in the agent configuration.",
        )

    else:
        raise IntentKitAPIError(
            400,
            "UnsupportedWalletProvider",
            f"Wallet provider '{agent.wallet_provider}' is not supported for signing. "
            "Supported providers are: 'cdp', 'native', 'safe', 'privy'.",
        )


__all__ = [
    "WalletProviderType",
    "WalletSignerType",
    "get_cdp_client",
    "get_cdp_network",
    "get_evm_account",
    "get_wallet_provider",
    "get_wallet_signer",
]
