"""User core functionality including server wallet creation."""

import logging
from typing import Any

from intentkit.config.config import config
from intentkit.models.user import UserUpdate
from intentkit.models.user_data import UserData

logger = logging.getLogger(__name__)

# Key used to store server wallet data in user_data table
USER_SERVER_WALLET_KEY = "server_wallet"


async def create_user_server_wallet(
    user_id: str,
    network_id: str = "base-mainnet",
    rpc_url: str | None = None,
    mode: str = "safe",  # "safe" or "privy"
) -> dict[str, Any]:
    """
    Create a server wallet for a user using either Safe (smart account) or Privy (EOA) mode.

    Mode options:
    - "safe": Creates Privy wallet + Safe smart account (default, for backwards compatibility)
    - "privy": Creates only Privy wallet, uses EOA address directly (no Safe, no spending limits)

    Unlike agent wallets, user server wallets do NOT have spending limits in either mode.

    The wallet data is stored in the user_data table with key "server_wallet"
    and the server_wallet_address is updated in the users table.

    Args:
        user_id: User ID (Privy user ID)
        network_id: The network to use (default: base-mainnet)
        rpc_url: Optional RPC URL override
        mode: Wallet mode - "safe" for Safe smart account or "privy" for EOA only

    Returns:
        dict: Wallet metadata including:
            - privy_wallet_id: The Privy wallet ID
            - privy_wallet_address: The Privy EOA address
            - smart_wallet_address: The Safe smart account address (only in "safe" mode)
            - provider: "safe" or "privy"
            - network_id: The network ID
            - chain_id: The chain ID

    Raises:
        ValueError: If network is not supported, RPC URL is not configured, or mode is invalid
        IntentKitAPIError: If wallet creation fails
    """
    if mode not in ("safe", "privy"):
        raise ValueError(f"Invalid mode: {mode}. Must be 'safe' or 'privy'")

    from intentkit.clients.privy import (
        CHAIN_CONFIGS,
        PrivyClient,
        deploy_safe_with_allowance,
    )

    chain_config = CHAIN_CONFIGS.get(network_id)
    if not chain_config:
        raise ValueError(f"Unsupported network: {network_id}")

    # Check if user already has a server wallet
    existing_data = await UserData.get(user_id, USER_SERVER_WALLET_KEY)
    if existing_data and existing_data.data:
        existing_wallet = existing_data.data
        if existing_wallet.get("smart_wallet_address"):
            logger.info(
                f"User {user_id} already has server wallet: "
                f"{existing_wallet['smart_wallet_address']}"
            )
            return existing_wallet

    # Get RPC URL from chain provider or config
    effective_rpc_url = rpc_url
    if not effective_rpc_url and config.chain_provider:
        try:
            chain_provider_config = config.chain_provider.get_chain_config(network_id)
            effective_rpc_url = chain_provider_config.rpc_url
        except Exception as e:
            logger.warning(f"Failed to get RPC URL from chain provider: {e}")

    if not effective_rpc_url:
        effective_rpc_url = chain_config.rpc_url

    if not effective_rpc_url:
        raise ValueError(f"No RPC URL configured for {network_id}")

    privy_client = PrivyClient()

    # Check for partial wallet creation (Privy wallet created but Safe failed)
    existing_privy_wallet_id: str | None = None
    existing_privy_wallet_address: str | None = None
    if existing_data and existing_data.data:
        partial_data = existing_data.data
        existing_privy_wallet_id = partial_data.get("privy_wallet_id")
        existing_privy_wallet_address = partial_data.get("privy_wallet_address")
        if existing_privy_wallet_id and existing_privy_wallet_address:
            logger.info(
                f"Found partial Privy wallet data for user {user_id}, "
                f"attempting recovery with wallet {existing_privy_wallet_id}"
            )

    # Create Privy wallet first (if not recovering)
    if not existing_privy_wallet_id:
        # Create a 1-of-N key quorum containing both the server's authorization key
        # and the user's ID. This allows either party to independently control the wallet.
        server_public_keys = privy_client.get_authorization_public_keys()
        owner_key_quorum_id = await privy_client.create_key_quorum(
            user_ids=[user_id],
            public_keys=server_public_keys if server_public_keys else None,
            authorization_threshold=1,  # Any single party can authorize
            display_name=f"intentkit:user:{user_id[:36]}",
        )
        # Create wallet with key quorum as owner (not additional signer)
        # This enables both server and user to fully control the wallet
        privy_wallet = await privy_client.create_wallet(
            owner_key_quorum_id=owner_key_quorum_id,
        )
        existing_privy_wallet_id = privy_wallet.id
        existing_privy_wallet_address = privy_wallet.address

        # Save partial data immediately for recovery
        partial_wallet_data = UserData(
            user_id=user_id,
            key=USER_SERVER_WALLET_KEY,
            data={
                "privy_wallet_id": existing_privy_wallet_id,
                "privy_wallet_address": existing_privy_wallet_address,
                "owner_key_quorum_id": owner_key_quorum_id,
                "network_id": network_id,
                "status": "privy_created",
            },
        )
        await partial_wallet_data.save()
        logger.info(
            f"Created Privy wallet {existing_privy_wallet_id} for user {user_id}"
        )

    # Assertions to ensure wallet data exists (for type checker)
    assert existing_privy_wallet_id is not None
    assert existing_privy_wallet_address is not None

    # Create wallet based on mode
    if mode == "safe":
        # Safe mode: Deploy Safe without spending limits (no allowance module)
        # Pass weekly_spending_limit_usdc=None to skip allowance module setup
        deployment_info = await deploy_safe_with_allowance(
            privy_client=privy_client,
            privy_wallet_id=existing_privy_wallet_id,
            privy_wallet_address=existing_privy_wallet_address,
            network_id=network_id,
            rpc_url=effective_rpc_url,
            weekly_spending_limit_usdc=None,  # No spending limits for user wallets
        )

        wallet_data: dict[str, Any] = {
            "privy_wallet_id": existing_privy_wallet_id,
            "privy_wallet_address": existing_privy_wallet_address,
            "smart_wallet_address": deployment_info["safe_address"],
            "provider": "safe",
            "network_id": network_id,
            "chain_id": chain_config.chain_id,
            "salt_nonce": deployment_info["salt_nonce"],
            "deployment_info": deployment_info,
            "status": "deployed",
        }

        server_wallet_address = deployment_info["safe_address"]
    else:
        # Privy mode: Use privy wallet address directly, no Safe deployment
        wallet_data = {
            "privy_wallet_id": existing_privy_wallet_id,
            "privy_wallet_address": existing_privy_wallet_address,
            "provider": "privy",
            "network_id": network_id,
            "chain_id": chain_config.chain_id,
            "status": "created",
        }

        server_wallet_address = existing_privy_wallet_address

    # Save complete wallet data
    final_wallet_data = UserData(
        user_id=user_id,
        key=USER_SERVER_WALLET_KEY,
        data=wallet_data,
    )
    await final_wallet_data.save()

    # Update user's server_wallet_address
    user_update = UserUpdate.model_construct(
        server_wallet_address=server_wallet_address,
    )
    await user_update.patch(user_id)

    logger.info(
        f"Created {mode} server wallet for user {user_id}: {server_wallet_address}"
    )

    return wallet_data


async def get_user_server_wallet(user_id: str) -> dict[str, Any] | None:
    """
    Get the server wallet data for a user.

    Args:
        user_id: User ID

    Returns:
        Wallet data dict or None if not found
    """
    user_data = await UserData.get(user_id, USER_SERVER_WALLET_KEY)
    if user_data and user_data.data:
        return user_data.data
    return None
