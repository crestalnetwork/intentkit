"""Morpho lending protocol skills."""

from typing import TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.morpho.base import MorphoBaseTool
from intentkit.skills.morpho.deposit import MorphoDeposit
from intentkit.skills.morpho.withdraw import MorphoWithdraw


class SkillStates(TypedDict):
    morpho_deposit: SkillState
    morpho_withdraw: SkillState


class Config(SkillConfig):
    """Configuration for Morpho skills."""

    states: SkillStates


# Cache for skill instances
_cache: dict[str, MorphoBaseTool] = {
    "morpho_deposit": MorphoDeposit(),
    "morpho_withdraw": MorphoWithdraw(),
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
