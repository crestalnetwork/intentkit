"""Team wallet provisioning.

Creates wallets owned by a team (see ``intentkit.models.wallet``). Agents
never own or bind wallets: web3 tools receive a wallet address chosen by the
agent from the team's pool, which is listed in its system prompt.
"""

import json
import logging

from epyxid import XID
from sqlalchemy import or_, select

from intentkit.config.config import config
from intentkit.config.db import get_session
from intentkit.models.team import Team
from intentkit.models.wallet import (
    DEFAULT_NETWORK_ID,
    WALLET_PROVIDERS,
    TeamWallet,
    wallet_owner_team,
)
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
    default_network_id: str | None = None,
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
    network = default_network_id or DEFAULT_NETWORK_ID

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
            default_network_id=network,
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
            default_network_id=network,
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
            default_network_id=network,
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
            default_network_id=network,
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
        default_network_id=network,
        evm_wallet_address=wallet_data["smart_wallet_address"],
        wallet_data=json.dumps(wallet_data),
        weekly_spending_limit=weekly_spending_limit,
        created_by=created_by,
    )


async def set_wallet_safe_token_spending_limit(
    team_id: str,
    wallet_id: str,
    token_address: str,
    spending_limit: float,
) -> dict:
    """Set a token spending limit on a team's Safe wallet (team-scoped)."""
    from intentkit.wallets.privy import PrivyClient, set_safe_token_spending_limit

    wallet = await TeamWallet.get_for_team(wallet_id, team_id)
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

    network_id = data.get("network_id") or wallet.network
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


async def update_team_wallet(
    team_id: str,
    wallet_id: str,
    *,
    name: str | None = None,
    default_network_id: str | None = None,
) -> TeamWallet:
    """Update a team wallet's mutable settings (name, default network).

    Raises:
        IntentKitAPIError 404: wallet missing or not owned by the team.
        IntentKitAPIError 400: the team already has a wallet with that name,
            or the wallet's network cannot be changed (safe/privy smart
            wallets are deployed on one chain).
    """
    wallet = await TeamWallet.get_for_team(wallet_id, team_id)
    if not wallet:
        raise IntentKitAPIError(404, "WalletNotFound", "Wallet not found")
    data: dict[str, str] = {}
    if name is not None:
        data["name"] = name
    if default_network_id is not None and default_network_id != wallet.network:
        if wallet.wallet_provider in ("safe", "privy"):
            raise IntentKitAPIError(
                400,
                "WalletNetworkImmutable",
                "Safe and Privy smart wallets are deployed on a single chain; "
                "their network cannot be changed after creation.",
            )
        data["default_network_id"] = default_network_id
    if not data:
        return wallet
    updated = await TeamWallet.patch(wallet_id, data)
    if updated is None:
        raise IntentKitAPIError(404, "WalletNotFound", "Wallet not found")
    return updated


async def delete_team_wallet(team_id: str, wallet_id: str) -> None:
    """Delete a team wallet.

    Deleting the team's LAST wallet is refused while any live team agent has
    web3 tools configured — agent create/update enforces "team owns a wallet"
    for web3 tools, and deletion must not silently break that invariant.
    Funds are NOT swept: the caller is expected to have emptied the wallet.

    Raises:
        IntentKitAPIError 404: wallet missing or not owned by the team.
        IntentKitAPIError 409: last wallet while web3-tool agents exist.
    """
    from intentkit.core.agent.tool_registry import filter_web3_tool_names
    from intentkit.models.agent.db import AgentTable

    wallet = await TeamWallet.get_for_team(wallet_id, team_id)
    if not wallet:
        raise IntentKitAPIError(404, "WalletNotFound", "Wallet not found")

    team_wallets = await TeamWallet.list_for_team(team_id)
    if len(team_wallets) <= 1:
        # Teamless agents belong to the synthetic "system" team by the
        # wallet_owner_team convention — the guard must see them too.
        team_filter = AgentTable.team_id == team_id
        if team_id == wallet_owner_team(None):
            team_filter = or_(
                AgentTable.team_id == team_id, AgentTable.team_id.is_(None)
            )
        async with get_session() as db:
            rows = (
                await db.execute(
                    select(AgentTable.id, AgentTable.name, AgentTable.tools).where(
                        team_filter,
                        AgentTable.archived_at.is_(None),
                        AgentTable.tools.isnot(None),
                    )
                )
            ).all()
        blocking = [
            str(name or agent_id)
            for agent_id, name, tools in rows
            if tools and filter_web3_tool_names(tools)
        ]
        if blocking:
            raise IntentKitAPIError(
                409,
                "WalletRequiredByAgents",
                "Cannot delete the team's last wallet: these agents have "
                f"web3 tools configured: {', '.join(blocking[:5])}",
            )

    await TeamWallet.delete(wallet_id)
