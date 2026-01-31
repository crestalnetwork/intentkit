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


# Legacy skill name mapping (old skill names -> new IntentKit names)
_LEGACY_NAME_MAP: dict[str, str] = {
    "MorphoActionProvider_deposit": "morpho_deposit",
    "MorphoActionProvider_withdraw": "morpho_withdraw",
}

# Skill registry
_SKILLS: dict[str, type[MorphoBaseTool]] = {
    "morpho_deposit": MorphoDeposit,
    "morpho_withdraw": MorphoWithdraw,
}

# Cache for skill instances
_cache: dict[str, MorphoBaseTool] = {}


def _normalize_skill_name(name: str) -> str:
    """Normalize legacy skill names to new names."""
    return _LEGACY_NAME_MAP.get(name, name)


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
            # Normalize legacy skill names
            normalized_name = _normalize_skill_name(skill_name)
            # Check cache first
            if normalized_name in _cache:
                tools.append(_cache[normalized_name])
            else:
                skill_class = _SKILLS.get(normalized_name)
                if skill_class:
                    skill_instance = skill_class()
                    _cache[normalized_name] = skill_instance
                    tools.append(skill_instance)

    return tools


def available() -> bool:
    """Check if this skill category is available based on system config.

    Morpho skills are available for any EVM-compatible wallet (CDP, Safe/Privy)
    on supported networks (base-mainnet, base-sepolia).
    """
    return True
