"""WETH wrapping/unwrapping skills."""

from typing import TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.weth.base import WethBaseTool
from intentkit.skills.weth.unwrap_eth import WETHUnwrapEth
from intentkit.skills.weth.wrap_eth import WETHWrapEth


class SkillStates(TypedDict):
    weth_wrap_eth: SkillState
    weth_unwrap_eth: SkillState


class Config(SkillConfig):
    """Configuration for WETH skills."""

    states: SkillStates


# Legacy skill name mapping (legacy names -> IntentKit names)
_LEGACY_NAME_MAP: dict[str, str] = {
    "WethActionProvider_wrap_eth": "weth_wrap_eth",
    "WethActionProvider_unwrap_eth": "weth_unwrap_eth",
}

# Skill registry
_SKILLS: dict[str, type[WethBaseTool]] = {
    "weth_wrap_eth": WETHWrapEth,
    "weth_unwrap_eth": WETHUnwrapEth,
}

# Cache for skill instances
_cache: dict[str, WethBaseTool] = {}


def _normalize_skill_name(name: str) -> str:
    """Normalize legacy skill names to new names."""
    return _LEGACY_NAME_MAP.get(name, name)


async def get_skills(
    config: Config,
    is_private: bool,
    **_,
) -> list[WethBaseTool]:
    """Get all enabled WETH skills.

    Args:
        config: The configuration for WETH skills.
        is_private: Whether to include private skills.

    Returns:
        A list of enabled WETH skills.
    """
    tools: list[WethBaseTool] = []

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

    WETH skills are available for any EVM-compatible wallet (CDP, Safe/Privy)
    on networks that have WETH deployed.
    """
    return True
