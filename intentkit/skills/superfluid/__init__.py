"""Superfluid streaming payment skills."""

from typing import TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.superfluid.base import SuperfluidBaseTool
from intentkit.skills.superfluid.create_flow import SuperfluidCreateFlow
from intentkit.skills.superfluid.delete_flow import SuperfluidDeleteFlow
from intentkit.skills.superfluid.update_flow import SuperfluidUpdateFlow


class SkillStates(TypedDict):
    superfluid_create_flow: SkillState
    superfluid_update_flow: SkillState
    superfluid_delete_flow: SkillState


class Config(SkillConfig):
    """Configuration for Superfluid skills."""

    states: SkillStates


# Cache for skill instances
_cache: dict[str, SuperfluidBaseTool] = {
    "superfluid_create_flow": SuperfluidCreateFlow(),
    "superfluid_update_flow": SuperfluidUpdateFlow(),
    "superfluid_delete_flow": SuperfluidDeleteFlow(),
}


async def get_skills(
    config: Config,
    is_private: bool,
    **_,
) -> list[SuperfluidBaseTool]:
    """Get all enabled Superfluid skills.

    Args:
        config: The configuration for Superfluid skills.
        is_private: Whether to include private skills.

    Returns:
        A list of enabled Superfluid skills.
    """
    tools: list[SuperfluidBaseTool] = []

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

    Superfluid skills are available for any EVM-compatible wallet (CDP, Safe/Privy).
    They don't require specific CDP credentials since they work with any wallet.
    """
    return True
