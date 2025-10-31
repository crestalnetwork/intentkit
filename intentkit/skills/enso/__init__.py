"""Enso skills."""

import logging
from typing import NotRequired, TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.enso.base import EnsoBaseTool
from intentkit.skills.enso.best_yield import EnsoGetBestYield
from intentkit.skills.enso.networks import EnsoGetNetworks
from intentkit.skills.enso.prices import EnsoGetPrices
from intentkit.skills.enso.route import EnsoRouteShortcut
from intentkit.skills.enso.tokens import EnsoGetTokens
from intentkit.skills.enso.wallet import (
    EnsoGetWalletApprovals,
    EnsoGetWalletBalances,
    EnsoWalletApprove,
)

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    get_networks: SkillState
    get_tokens: SkillState
    get_prices: SkillState
    get_wallet_approvals: SkillState
    get_wallet_balances: SkillState
    wallet_approve: SkillState
    route_shortcut: SkillState
    get_best_yield: SkillState


class Config(SkillConfig):
    """Configuration for Enso skills."""

    states: SkillStates
    api_token: NotRequired[str]
    main_tokens: NotRequired[list[str]]


async def get_skills(
    config: Config,
    is_private: bool,
    **_,
) -> list[EnsoBaseTool]:
    """Get all Enso skills."""
    available_skills = []

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    # Get each skill using the cached getter
    result = []
    for name in available_skills:
        skill = get_enso_skill(name)
        if skill:
            result.append(skill)
    return result


def get_enso_skill(
    name: str,
) -> EnsoBaseTool:
    """Get an Enso skill by name.

    Args:
        name: The name of the skill to get

    Returns:
        The requested Enso skill
    """
    if name == "get_networks":
        return EnsoGetNetworks()
    if name == "get_tokens":
        return EnsoGetTokens()
    if name == "get_prices":
        return EnsoGetPrices()
    if name == "get_wallet_approvals":
        return EnsoGetWalletApprovals()
    if name == "get_wallet_balances":
        return EnsoGetWalletBalances()
    if name == "wallet_approve":
        return EnsoWalletApprove()
    if name == "route_shortcut":
        return EnsoRouteShortcut()
    if name == "get_best_yield":
        return EnsoGetBestYield()
    else:
        logger.warning(f"Unknown Enso skill: {name}")
        return None
