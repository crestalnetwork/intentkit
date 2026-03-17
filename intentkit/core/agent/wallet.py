import json
import logging
from decimal import Decimal
from typing import Any

from intentkit.config.config import config
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


async def process_agent_wallet(
    agent: Agent,
    old_wallet_provider: str | None = None,
    old_weekly_spending_limit: float | None = None,
) -> AgentData:
    """Process agent wallet initialization and validation.

    Args:
        agent: The agent that was created or updated
        old_wallet_provider: Previous wallet provider (None, "cdp", or "readonly")

    Returns:
        AgentData: The processed agent data

    Raises:
        IntentKitAPIError: If attempting to change between cdp and readonly providers
    """
    current_wallet_provider = agent.wallet_provider
    old_limit = (
        Decimal(str(old_weekly_spending_limit)).quantize(Decimal("0.000001"))
        if old_weekly_spending_limit is not None
        else None
    )
    new_limit = (
        Decimal(str(agent.weekly_spending_limit)).quantize(Decimal("0.000001"))
        if agent.weekly_spending_limit is not None
        else None
    )

    if (
        old_wallet_provider is not None
        and old_wallet_provider != "none"
        and old_wallet_provider != current_wallet_provider
    ):
        raise IntentKitAPIError(
            400,
            "WalletProviderChangeNotAllowed",
            "Cannot change wallet provider once set",
        )

    if (
        old_wallet_provider is not None
        and old_wallet_provider != "none"
        and old_wallet_provider == current_wallet_provider
    ):
        if current_wallet_provider in ("safe", "privy") and old_limit != new_limit:
            agent_data = await AgentData.get(agent.id)
            if agent_data.privy_wallet_data:
                if current_wallet_provider == "safe":
                    from intentkit.wallets.privy import create_privy_safe_wallet

                    try:
                        privy_wallet_data = json.loads(agent_data.privy_wallet_data)
                    except json.JSONDecodeError:
                        privy_wallet_data = {}

                    existing_privy_wallet_id = privy_wallet_data.get("privy_wallet_id")
                    existing_privy_wallet_address = privy_wallet_data.get(
                        "privy_wallet_address"
                    )

                    if existing_privy_wallet_id and existing_privy_wallet_address:
                        rpc_url: str | None = None
                        network_id = (
                            agent.network_id
                            or privy_wallet_data.get("network_id")
                            or "base-mainnet"
                        )
                        if config.chain_provider:
                            try:
                                chain_config = config.chain_provider.get_chain_config(
                                    network_id
                                )
                                rpc_url = chain_config.rpc_url
                            except Exception as e:
                                logger.warning(
                                    f"Failed to get RPC URL from chain provider: {e}"
                                )

                        wallet_data = await create_privy_safe_wallet(
                            agent_id=agent.id,
                            network_id=network_id,
                            rpc_url=rpc_url,
                            weekly_spending_limit_usdc=agent.weekly_spending_limit
                            if agent.weekly_spending_limit is not None
                            else 0.0,
                            existing_privy_wallet_id=existing_privy_wallet_id,
                            existing_privy_wallet_address=existing_privy_wallet_address,
                        )
                        agent_data = await AgentData.patch(
                            agent.id,
                            {
                                "evm_wallet_address": wallet_data[
                                    "smart_wallet_address"
                                ],
                                "privy_wallet_data": json.dumps(wallet_data),
                            },
                        )
                        return agent_data
        return await AgentData.get(agent.id)

    agent_data = await AgentData.get(agent.id)
    if agent_data.evm_wallet_address:
        return agent_data

    if config.cdp_api_key_id and current_wallet_provider == "cdp":
        from intentkit.wallets.cdp import get_wallet_provider as get_cdp_wallet_provider

        await get_cdp_wallet_provider(agent)
        agent_data = await AgentData.get(agent.id)
    elif current_wallet_provider == "readonly":
        agent_data = await AgentData.patch(
            agent.id,
            {
                "evm_wallet_address": agent.readonly_wallet_address,
            },
        )
    elif current_wallet_provider == "safe":
        from intentkit.wallets.privy import create_privy_safe_wallet

        rpc_url: str | None = None
        network_id = agent.network_id or "base-mainnet"
        if config.chain_provider:
            try:
                chain_config = config.chain_provider.get_chain_config(network_id)
                rpc_url = chain_config.rpc_url
            except Exception as e:
                logger.warning("Failed to get RPC URL from chain provider: %s", e)

        existing_privy_wallet_id: str | None = None
        existing_privy_wallet_address: str | None = None
        if agent_data.privy_wallet_data:
            try:
                partial_data = json.loads(agent_data.privy_wallet_data)
                existing_privy_wallet_id = partial_data.get("privy_wallet_id")
                existing_privy_wallet_address = partial_data.get("privy_wallet_address")
                if existing_privy_wallet_id and existing_privy_wallet_address:
                    logger.info(
                        "Found partial Privy wallet data for agent %s, "
                        "attempting recovery with wallet %s",
                        agent.id,
                        existing_privy_wallet_id,
                    )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to parse existing privy_wallet_data: %s", e)

        if not existing_privy_wallet_id:
            from intentkit.wallets.privy import PrivyClient

            privy_client = PrivyClient()
            if not agent.owner:
                raise IntentKitAPIError(
                    400,
                    "PrivyUserIdMissing",
                    "Agent owner (Privy user ID) is required for Privy wallets",
                )
            if not agent.owner.startswith("did:privy:"):
                raise IntentKitAPIError(
                    400,
                    "PrivyUserIdInvalid",
                    "Only Privy-authenticated users (did:privy:...) can create Privy wallets",
                )
            server_public_keys = privy_client.get_authorization_public_keys()
            owner_key_quorum_id = await privy_client.create_key_quorum(
                user_ids=[agent.owner],
                public_keys=server_public_keys if server_public_keys else None,
                authorization_threshold=1,
                display_name=f"intentkit:{agent.id[:40]}",
            )
            privy_wallet = await privy_client.create_wallet(
                owner_key_quorum_id=owner_key_quorum_id,
            )
            existing_privy_wallet_id = privy_wallet.id
            existing_privy_wallet_address = privy_wallet.address

            partial_wallet_data = {
                "privy_wallet_id": existing_privy_wallet_id,
                "privy_wallet_address": existing_privy_wallet_address,
                "owner_key_quorum_id": owner_key_quorum_id,
                "network_id": network_id,
                "status": "privy_created",
            }
            await AgentData.patch(
                agent.id,
                {"privy_wallet_data": json.dumps(partial_wallet_data)},
            )
            logger.info(
                f"Created Privy wallet {existing_privy_wallet_id} for agent {agent.id}"
            )

        wallet_data = await create_privy_safe_wallet(
            agent_id=agent.id,
            network_id=network_id,
            rpc_url=rpc_url,
            weekly_spending_limit_usdc=agent.weekly_spending_limit,
            existing_privy_wallet_id=existing_privy_wallet_id,
            existing_privy_wallet_address=existing_privy_wallet_address,
        )
        agent_data = await AgentData.patch(
            agent.id,
            {
                "evm_wallet_address": wallet_data["smart_wallet_address"],
                "privy_wallet_data": json.dumps(wallet_data),
            },
        )
    elif current_wallet_provider == "privy":
        from intentkit.wallets.privy import PrivyClient

        privy_client = PrivyClient()
        if not agent.owner:
            raise IntentKitAPIError(
                400,
                "PrivyUserIdMissing",
                "Agent owner (Privy user ID) is required for Privy wallets",
            )
        if not agent.owner.startswith("did:privy:"):
            raise IntentKitAPIError(
                400,
                "PrivyUserIdInvalid",
                "Only Privy-authenticated users (did:privy:...) can create Privy wallets",
            )

        server_public_keys = privy_client.get_authorization_public_keys()
        owner_key_quorum_id = await privy_client.create_key_quorum(
            user_ids=[agent.owner],
            public_keys=server_public_keys if server_public_keys else None,
            authorization_threshold=1,
            display_name=f"intentkit:{agent.id[:40]}",
        )

        privy_wallet = await privy_client.create_wallet(
            owner_key_quorum_id=owner_key_quorum_id,
        )

        wallet_data = {
            "privy_wallet_id": privy_wallet.id,
            "privy_wallet_address": privy_wallet.address,
            "owner_key_quorum_id": owner_key_quorum_id,
            "network_id": agent.network_id or "base-mainnet",
            "provider": "privy",
            "status": "created",
        }

        agent_data = await AgentData.patch(
            agent.id,
            {
                "evm_wallet_address": privy_wallet.address,
                "privy_wallet_data": json.dumps(wallet_data),
            },
        )
        logger.info(
            f"Created Privy-only wallet {privy_wallet.id} for agent {agent.id}, address: {privy_wallet.address}"
        )
    elif current_wallet_provider == "native":
        from intentkit.wallets.native import create_native_wallet

        network_id = agent.network_id or "base-mainnet"
        wallet_data = create_native_wallet(network_id)

        agent_data = await AgentData.patch(
            agent.id,
            {
                "evm_wallet_address": wallet_data["address"],
                "native_wallet_data": json.dumps(wallet_data),
            },
        )
        logger.info(
            f"Created native wallet for agent {agent.id}, address: {wallet_data['address']}"
        )

    return agent_data


def _resolve_safe_rpc_url(network_id: str, privy_wallet_data: dict[str, Any]) -> str:
    rpc_url = privy_wallet_data.get("rpc_url")
    if not rpc_url and config.chain_provider:
        try:
            chain_config = config.chain_provider.get_chain_config(network_id)
            rpc_url = chain_config.rpc_url
        except Exception as e:
            logger.warning("Failed to get RPC URL from chain provider: %s", e)

    if not rpc_url:
        from intentkit.wallets.privy import CHAIN_CONFIGS

        chain_config = CHAIN_CONFIGS.get(network_id)
        if chain_config and chain_config.rpc_url:
            rpc_url = chain_config.rpc_url

    if not rpc_url:
        raise IntentKitAPIError(
            500,
            "RpcUrlNotConfigured",
            f"RPC URL not configured for network {network_id}",
        )

    return rpc_url


async def set_agent_safe_token_spending_limit(
    agent_id: str,
    token_address: str,
    spending_limit: float,
) -> dict[str, Any]:
    """Set token spending limit for a Safe agent using agent-level inputs only."""
    from intentkit.core.agent.queries import get_agent
    from intentkit.wallets.privy import PrivyClient, set_safe_token_spending_limit

    agent = await get_agent(agent_id)
    if not agent:
        raise IntentKitAPIError(
            status_code=404,
            key="AgentNotFound",
            message=f"Agent with ID '{agent_id}' not found",
        )
    if agent.wallet_provider != "safe":
        raise IntentKitAPIError(
            400,
            "SafeWalletRequired",
            "Token spending limits can only be set for agents using wallet_provider='safe'.",
        )

    agent_data = await AgentData.get(agent_id)
    if not agent_data.privy_wallet_data:
        raise IntentKitAPIError(
            400,
            "PrivyWalletDataMissing",
            "Privy wallet data is missing for this Safe wallet agent.",
        )

    try:
        privy_wallet_data = json.loads(agent_data.privy_wallet_data)
    except json.JSONDecodeError as e:
        raise IntentKitAPIError(
            500,
            "PrivyWalletDataInvalid",
            "Privy wallet data is corrupted and cannot be parsed.",
        ) from e

    try:
        privy_wallet_id = privy_wallet_data["privy_wallet_id"]
        privy_wallet_address = privy_wallet_data["privy_wallet_address"]
        safe_address = privy_wallet_data["smart_wallet_address"]
    except KeyError as e:
        raise IntentKitAPIError(
            500,
            "PrivyWalletDataIncomplete",
            "Privy wallet data is missing required fields.",
        ) from e

    network_id = (
        privy_wallet_data.get("network_id") or agent.network_id or "base-mainnet"
    )
    rpc_url = _resolve_safe_rpc_url(network_id, privy_wallet_data)

    privy_client = PrivyClient()
    return await set_safe_token_spending_limit(
        privy_client=privy_client,
        privy_wallet_id=privy_wallet_id,
        privy_wallet_address=privy_wallet_address,
        safe_address=safe_address,
        token_address=token_address,
        spending_limit=spending_limit,
        network_id=network_id,
        rpc_url=rpc_url,
    )
