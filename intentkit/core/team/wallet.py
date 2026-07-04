"""Team wallet provisioning.

Creates wallets owned by a team (see ``intentkit.models.wallet``). This is
the team-level successor of the removed per-agent provisioning: agents no
longer own wallets, they are only authorized to use one of their team's
wallets via ``Agent.wallet_id``.
"""

import json
import logging

from epyxid import XID

from intentkit.config.config import config
from intentkit.models.team import Team
from intentkit.models.wallet import WALLET_PROVIDERS, TeamWallet
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


async def _resolve_privy_owner(team_id: str, created_by: str) -> str:
    """Pick the Privy user that anchors a new wallet's key quorum.

    Privy key quorums are bound to a Privy user id. Prefer the creating user
    when they authenticated via Privy, else fall back to the team owner.
    """
    if created_by.startswith("did:privy:"):
        return created_by
    owner = await Team.get_owner(team_id)
    if owner and owner.startswith("did:privy:"):
        return owner
    raise IntentKitAPIError(
        400,
        "PrivyUserIdMissing",
        "Privy/Safe wallets require a Privy-authenticated user (did:privy:...) "
        "as creator or team owner.",
    )


def _resolve_rpc_url(network_id: str) -> str | None:
    if config.chain_provider:
        try:
            return config.chain_provider.get_chain_config(network_id).rpc_url
        except Exception as e:
            logger.warning("Failed to get RPC URL from chain provider: %s", e)
    from intentkit.wallets.privy import CHAIN_CONFIGS

    chain_config = CHAIN_CONFIGS.get(network_id)
    return chain_config.rpc_url if chain_config else None


async def create_team_wallet(
    *,
    team_id: str,
    name: str,
    wallet_provider: str,
    created_by: str,
    network_id: str | None = None,
    readonly_address: str | None = None,
    weekly_spending_limit: float | None = None,
) -> TeamWallet:
    """Provision a new wallet for a team and persist it."""
    if wallet_provider not in WALLET_PROVIDERS:
        raise IntentKitAPIError(
            400,
            "UnsupportedWalletProvider",
            f"Wallet provider '{wallet_provider}' is not supported. "
            f"Supported providers: {', '.join(WALLET_PROVIDERS)}.",
        )

    wallet_id = str(XID())
    network = network_id or "base-mainnet"

    if wallet_provider == "cdp":
        if not config.cdp_api_key_id:
            raise IntentKitAPIError(
                500, "CdpNotConfigured", "CDP API keys are not configured."
            )
        from intentkit.wallets.cdp import get_cdp_client

        account = await get_cdp_client().evm.create_account(name=wallet_id)
        return await TeamWallet.create(
            wallet_id=wallet_id,
            team_id=team_id,
            name=name,
            wallet_provider="cdp",
            network_id=network,
            evm_wallet_address=account.address,
            created_by=created_by,
        )

    if wallet_provider == "native":
        from intentkit.wallets.native import create_native_wallet

        wallet_data = create_native_wallet(network)
        return await TeamWallet.create(
            wallet_id=wallet_id,
            team_id=team_id,
            name=name,
            wallet_provider="native",
            network_id=network,
            evm_wallet_address=wallet_data["address"],
            wallet_data=json.dumps(wallet_data),
            created_by=created_by,
        )

    if wallet_provider == "readonly":
        if not readonly_address:
            raise IntentKitAPIError(
                400,
                "ReadonlyAddressRequired",
                "readonly_address is required for readonly wallets.",
            )
        return await TeamWallet.create(
            wallet_id=wallet_id,
            team_id=team_id,
            name=name,
            wallet_provider="readonly",
            network_id=network,
            evm_wallet_address=readonly_address,
            created_by=created_by,
        )

    # privy and safe both start from a Privy server wallet
    from intentkit.wallets.privy import PrivyClient

    privy_owner = await _resolve_privy_owner(team_id, created_by)
    privy_client = PrivyClient()
    server_public_keys = privy_client.get_authorization_public_keys()
    owner_key_quorum_id = await privy_client.create_key_quorum(
        user_ids=[privy_owner],
        public_keys=server_public_keys if server_public_keys else None,
        authorization_threshold=1,
        display_name=f"intentkit:wallet:{wallet_id}",
    )
    privy_wallet = await privy_client.create_wallet(
        owner_key_quorum_id=owner_key_quorum_id,
    )

    if wallet_provider == "privy":
        wallet_data = {
            "privy_wallet_id": privy_wallet.id,
            "privy_wallet_address": privy_wallet.address,
            "owner_key_quorum_id": owner_key_quorum_id,
            "network_id": network,
            "provider": "privy",
            "status": "created",
        }
        return await TeamWallet.create(
            wallet_id=wallet_id,
            team_id=team_id,
            name=name,
            wallet_provider="privy",
            network_id=network,
            evm_wallet_address=privy_wallet.address,
            wallet_data=json.dumps(wallet_data),
            created_by=created_by,
        )

    # safe: deploy a Safe smart account on top of the Privy wallet
    from intentkit.wallets.privy import create_privy_safe_wallet

    wallet_data = await create_privy_safe_wallet(
        agent_id=wallet_id,
        network_id=network,
        rpc_url=_resolve_rpc_url(network),
        weekly_spending_limit_usdc=weekly_spending_limit,
        existing_privy_wallet_id=privy_wallet.id,
        existing_privy_wallet_address=privy_wallet.address,
    )
    wallet_data["owner_key_quorum_id"] = owner_key_quorum_id
    return await TeamWallet.create(
        wallet_id=wallet_id,
        team_id=team_id,
        name=name,
        wallet_provider="safe",
        network_id=network,
        evm_wallet_address=wallet_data["smart_wallet_address"],
        wallet_data=json.dumps(wallet_data),
        weekly_spending_limit=weekly_spending_limit,
        created_by=created_by,
    )


async def set_wallet_safe_token_spending_limit(
    wallet_id: str,
    token_address: str,
    spending_limit: float,
) -> dict:
    """Set a token spending limit on a team's Safe wallet."""
    from intentkit.wallets.privy import PrivyClient, set_safe_token_spending_limit

    wallet = await TeamWallet.get(wallet_id)
    if not wallet:
        raise IntentKitAPIError(404, "WalletNotFound", "Wallet not found")
    if wallet.wallet_provider != "safe":
        raise IntentKitAPIError(
            400,
            "SafeWalletRequired",
            "Token spending limits can only be set on Safe wallets.",
        )

    data = wallet.wallet_data_json()
    try:
        privy_wallet_id = data["privy_wallet_id"]
        privy_wallet_address = data["privy_wallet_address"]
        safe_address = data["smart_wallet_address"]
    except KeyError as e:
        raise IntentKitAPIError(
            500,
            "PrivyWalletDataIncomplete",
            "Wallet data is missing required fields.",
        ) from e

    network_id = data.get("network_id") or wallet.network_id or "base-mainnet"
    rpc_url = data.get("rpc_url") or _resolve_rpc_url(network_id)
    if not rpc_url:
        raise IntentKitAPIError(
            500,
            "RpcUrlNotConfigured",
            f"RPC URL not configured for network {network_id}",
        )

    # Note: the weekly_spending_limit column tracks the USDC limit chosen at
    # creation; per-token allowances set here live on-chain in the allowance
    # module and are not mirrored into the row.
    return await set_safe_token_spending_limit(
        privy_client=PrivyClient(),
        privy_wallet_id=privy_wallet_id,
        privy_wallet_address=privy_wallet_address,
        safe_address=safe_address,
        token_address=token_address,
        spending_limit=spending_limit,
        network_id=network_id,
        rpc_url=rpc_url,
    )
