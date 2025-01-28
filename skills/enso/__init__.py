"""Enso skills."""

from cdp import Wallet

from abstracts.skill import SkillStoreABC
from skills.enso.base import EnsoBaseTool
from skills.enso.networks import EnsoGetNetworks
from skills.enso.prices import EnsoGetPrices
from skills.enso.route import EnsoRouteShortcut
from skills.enso.tokens import EnsoGetTokens
from skills.enso.wallet import (
    EnsoBroadcastWalletApprove,
    EnsoGetWalletApprovals,
    EnsoGetWalletBalances,
)


def get_enso_skill(
    name: str,
    api_token: str,
    main_tokens: list[str],
    wallet: Wallet,
    rpc_nodes: dict[str, str],
    store: SkillStoreABC,
    agent_id: str,
) -> EnsoBaseTool:
    if not api_token:
        raise ValueError("Enso API token is empty")

    if name == "get_networks":
        return EnsoGetNetworks(
            api_token=api_token,
            main_tokens=main_tokens,
            store=store,
            agent_id=agent_id,
        )

    if name == "get_tokens":
        return EnsoGetTokens(
            api_token=api_token,
            main_tokens=main_tokens,
            store=store,
            agent_id=agent_id,
        )

    if name == "get_prices":
        return EnsoGetPrices(
            api_token=api_token,
            main_tokens=main_tokens,
            store=store,
            agent_id=agent_id,
        )

    if name == "get_wallet_approvals":
        if not wallet:
            raise ValueError("Wallet is empty")
        return EnsoGetWalletApprovals(
            api_token=api_token,
            main_tokens=main_tokens,
            wallet=wallet,
            store=store,
            agent_id=agent_id,
        )

    if name == "get_wallet_balances":
        if not wallet:
            raise ValueError("Wallet is empty")
        return EnsoGetWalletBalances(
            api_token=api_token,
            main_tokens=main_tokens,
            wallet=wallet,
            store=store,
            agent_id=agent_id,
        )

    if name == "wallet_approve":
        if not wallet:
            raise ValueError("Wallet is empty")
        return EnsoBroadcastWalletApprove(
            api_token=api_token,
            main_tokens=main_tokens,
            wallet=wallet,
            rpc_nodes=rpc_nodes,
            store=store,
            agent_id=agent_id,
        )

    if name == "broadcast_route_shortcut":
        if not wallet:
            raise ValueError("Wallet is empty")
        return EnsoRouteShortcut(
            api_token=api_token,
            main_tokens=main_tokens,
            wallet=wallet,
            rpc_nodes=rpc_nodes,
            store=store,
            agent_id=agent_id,
        )

    else:
        raise ValueError(f"Unknown Enso skill: {name}")
