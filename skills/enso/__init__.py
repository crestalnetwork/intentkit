"""Enso skills."""

from abstracts.skill import SkillStoreABC
from skills.enso.base import EnsoBaseTool
from skills.enso.networks import EnsoGetNetworks
from skills.enso.prices import EnsoGetPrices
from skills.enso.route import EnsoGetRouteShortcut
from skills.enso.tokens import EnsoGetTokens
from skills.enso.wallet import (
    EnsoGetWalletApprovals,
    EnsoGetWalletApprove,
    EnsoGetWalletBalances,
)


def get_enso_skill(
    name: str,
    api_token: str,
    main_tokens: list[str],
    from_address: str,
    store: SkillStoreABC,
    agent_id: str,
) -> EnsoBaseTool:
    if not api_token:
        raise ValueError("Enso API token is empty")

    if name == "get_networks":
        return EnsoGetNetworks(
            api_token=api_token,
            main_tokens=main_tokens,
            from_address=from_address,
            store=store,
            agent_id=agent_id,
        )
    if name == "get_tokens":
        return EnsoGetTokens(
            api_token=api_token,
            main_tokens=main_tokens,
            from_address=from_address,
            store=store,
            agent_id=agent_id,
        )
    if name == "get_route_shortcut":
        return EnsoGetRouteShortcut(
            api_token=api_token,
            main_tokens=main_tokens,
            from_address=from_address,
            store=store,
            agent_id=agent_id,
        )
    if name == "get_wallet_approve":
        return EnsoGetWalletApprove(
            api_token=api_token,
            main_tokens=main_tokens,
            from_address=from_address,
            store=store,
            agent_id=agent_id,
        )
    if name == "get_wallet_approvals":
        return EnsoGetWalletApprovals(
            api_token=api_token,
            main_tokens=main_tokens,
            from_address=from_address,
            store=store,
            agent_id=agent_id,
        )
    if name == "get_wallet_balances":
        return EnsoGetWalletBalances(
            api_token=api_token,
            main_tokens=main_tokens,
            from_address=from_address,
            store=store,
            agent_id=agent_id,
        )
    if name == "get_prices":
        return EnsoGetPrices(
            api_token=api_token,
            main_tokens=main_tokens,
            from_address=from_address,
            store=store,
            agent_id=agent_id,
        )

    else:
        raise ValueError(f"Unknown Enso skill: {name}")
