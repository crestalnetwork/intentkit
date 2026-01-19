"""
IntentKit clients module.

This module provides unified access to various client implementations,
including wallet providers that support both CDP and Privy backends.
"""

import json
import logging
from typing import TYPE_CHECKING, Any, Union

from intentkit.clients.cdp import (
    get_cdp_client,
    get_cdp_network,
    get_evm_account,
)
from intentkit.clients.cdp import (
    get_wallet_provider as get_cdp_wallet_provider,
)
from intentkit.clients.twitter import (
    TwitterClient,
    TwitterClientConfig,
    get_twitter_client,
)
from intentkit.clients.web3 import get_web3_client
from intentkit.utils.error import IntentKitAPIError

if TYPE_CHECKING:
    from coinbase_agentkit import CdpEvmWalletProvider

    from intentkit.clients.privy import SafeWalletProvider
    from intentkit.models.agent import Agent

logger = logging.getLogger(__name__)

# Type alias for unified wallet provider
WalletProviderType = Union["CdpEvmWalletProvider", "SafeWalletProvider"]
WalletSignerType = Any  # Can be ThreadSafeEvmWalletSigner or PrivyWalletSigner


async def get_wallet_provider(agent: "Agent") -> WalletProviderType:
    """
    Get wallet provider based on agent's wallet_provider setting.

    This function automatically selects the appropriate wallet provider
    implementation based on the agent's configuration.

    Args:
        agent: The agent to get the wallet provider for.

    Returns:
        CdpEvmWalletProvider for CDP agents.
        SafeWalletProvider for Safe agents (Privy + Safe smart account).

    Raises:
        IntentKitAPIError: If the wallet provider is not supported or not configured.
    """
    if agent.wallet_provider == "cdp":
        return await get_cdp_wallet_provider(agent)

    elif agent.wallet_provider in ("safe", "privy"):
        from intentkit.clients.privy import get_wallet_provider as get_privy_provider
        from intentkit.models.agent_data import AgentData

        agent_data = await AgentData.get(agent.id)
        if not agent_data.privy_wallet_data:
            raise IntentKitAPIError(
                400,
                "PrivyWalletNotInitialized",
                f"Wallet has not been initialized for this agent. "
                f"Please ensure the agent was created with wallet_provider='{agent.wallet_provider}'.",
            )

        try:
            privy_data = json.loads(agent_data.privy_wallet_data)
        except json.JSONDecodeError as e:
            raise IntentKitAPIError(
                500,
                "PrivyWalletDataCorrupted",
                f"Failed to parse wallet data: {e}",
            ) from e

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
            "Please set wallet_provider to 'cdp', 'safe', or 'privy' in the agent configuration.",
        )

    else:
        raise IntentKitAPIError(
            400,
            "UnsupportedWalletProvider",
            f"Wallet provider '{agent.wallet_provider}' is not supported for on-chain operations. "
            "Supported providers are: 'cdp', 'safe', 'privy'.",
        )


async def get_wallet_signer(agent: "Agent") -> WalletSignerType:
    """
    Get EVM signer based on agent's wallet_provider setting.

    This function returns a signer compatible with eth_account interfaces,
    suitable for use with libraries like x402 that require signing capabilities.

    Args:
        agent: The agent to get the wallet signer for.

    Returns:
        A signer object with sign_message, sign_typed_data, and unsafe_sign_hash methods.
        - For CDP: ThreadSafeEvmWalletSigner wrapping CdpEvmWalletProvider
        - For Safe/Privy: PrivyWalletSigner

    Raises:
        IntentKitAPIError: If the wallet provider is not supported or not configured.
    """
    if agent.wallet_provider == "cdp":
        # Import here to avoid circular imports
        from intentkit.clients.cdp import get_wallet_provider as get_cdp_provider

        provider = await get_cdp_provider(agent)

        # Create thread-safe signer wrapper
        from intentkit.clients.signer import ThreadSafeEvmWalletSigner

        return ThreadSafeEvmWalletSigner(provider)

    elif agent.wallet_provider in ("safe", "privy"):
        from intentkit.clients.privy import get_wallet_signer as get_privy_signer
        from intentkit.models.agent_data import AgentData

        agent_data = await AgentData.get(agent.id)
        if not agent_data.privy_wallet_data:
            raise IntentKitAPIError(
                400,
                "PrivyWalletNotInitialized",
                f"Wallet has not been initialized for this agent. "
                f"Please ensure the agent was created with wallet_provider='{agent.wallet_provider}'.",
            )

        try:
            privy_data = json.loads(agent_data.privy_wallet_data)
        except json.JSONDecodeError as e:
            raise IntentKitAPIError(
                500,
                "PrivyWalletDataCorrupted",
                f"Failed to parse wallet data: {e}",
            ) from e

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
            "Please set wallet_provider to 'cdp', 'safe', or 'privy' in the agent configuration.",
        )

    else:
        raise IntentKitAPIError(
            400,
            "UnsupportedWalletProvider",
            f"Wallet provider '{agent.wallet_provider}' is not supported for signing. "
            "Supported providers are: 'cdp', 'safe', 'privy'.",
        )


# Legacy alias for backwards compatibility
# This now routes to the unified function
get_cdp_wallet_provider_legacy = get_cdp_wallet_provider

__all__ = [
    # Twitter client
    "TwitterClient",
    "TwitterClientConfig",
    "get_twitter_client",
    # CDP specific (for backwards compatibility)
    "get_evm_account",
    "get_cdp_client",
    "get_cdp_network",
    # Web3
    "get_web3_client",
    # Unified wallet functions (recommended)
    "get_wallet_provider",
    "get_wallet_signer",
]
