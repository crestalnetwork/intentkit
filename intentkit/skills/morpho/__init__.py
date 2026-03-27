"""Morpho lending protocol skills."""

from typing import TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.morpho.base import MorphoBaseTool
from intentkit.skills.morpho.borrow import MorphoBorrow
from intentkit.skills.morpho.deposit import MorphoDeposit
from intentkit.skills.morpho.get_position import MorphoGetPosition
from intentkit.skills.morpho.get_vault_data import MorphoGetVaultData
from intentkit.skills.morpho.repay import MorphoRepay
from intentkit.skills.morpho.supply_collateral import MorphoSupplyCollateral
from intentkit.skills.morpho.withdraw import MorphoWithdraw
from intentkit.skills.morpho.withdraw_collateral import MorphoWithdrawCollateral


class SkillStates(TypedDict):
    morpho_deposit: SkillState
    morpho_withdraw: SkillState
    morpho_get_vault_data: SkillState
    morpho_supply_collateral: SkillState
    morpho_withdraw_collateral: SkillState
    morpho_borrow: SkillState
    morpho_repay: SkillState
    morpho_get_position: SkillState


class Config(SkillConfig):
    """Configuration for Morpho skills."""

    states: SkillStates


# Cache for skill instances
_cache: dict[str, MorphoBaseTool] = {
    "morpho_deposit": MorphoDeposit(),
    "morpho_withdraw": MorphoWithdraw(),
    "morpho_get_vault_data": MorphoGetVaultData(),
    "morpho_supply_collateral": MorphoSupplyCollateral(),
    "morpho_withdraw_collateral": MorphoWithdrawCollateral(),
    "morpho_borrow": MorphoBorrow(),
    "morpho_repay": MorphoRepay(),
    "morpho_get_position": MorphoGetPosition(),
}


async def get_skills(
    config: Config,
    is_private: bool,
    **_,
) -> list[MorphoBaseTool]:
    """Get all enabled Morpho skills.

    Args:
        config: The configuration for Morpho skills.
        is_private: Whether to include private skills.

    Returns:
        A list of enabled Morpho skills.
    """
    tools: list[MorphoBaseTool] = []

    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        if state == "public" or (state == "private" and is_private):
            # Check cache first
            if skill_name in _cache:
                tools.append(_cache[skill_name])

    return tools


def available() -> bool:
    """Check if this skill category is available based on system config.

    Morpho skills are available for any EVM-compatible wallet (CDP, Safe/Privy)
    on supported networks (base-mainnet, base-sepolia).
    """
    return True
