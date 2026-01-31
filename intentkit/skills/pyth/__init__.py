"""Pyth price oracle skills."""

from typing import TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.pyth.base import PythBaseTool
from intentkit.skills.pyth.fetch_price import PythFetchPrice
from intentkit.skills.pyth.fetch_price_feed import PythFetchPriceFeed


class SkillStates(TypedDict):
    pyth_fetch_price: SkillState
    pyth_fetch_price_feed: SkillState


class Config(SkillConfig):
    """Configuration for Pyth skills."""

    states: SkillStates


# Skill registry
_SKILLS: dict[str, type[PythBaseTool]] = {
    "pyth_fetch_price": PythFetchPrice,
    "pyth_fetch_price_feed": PythFetchPriceFeed,
}

# Legacy skill name mapping (legacy names -> IntentKit names)
_LEGACY_NAME_MAP: dict[str, str] = {
    "PythActionProvider_fetch_price": "pyth_fetch_price",
    "PythActionProvider_fetch_price_feed": "pyth_fetch_price_feed",
}

# Cache for stateless skills
_cache: dict[str, PythBaseTool] = {}


def _normalize_skill_name(name: str) -> str:
    """Normalize legacy skill names to new names."""
    return _LEGACY_NAME_MAP.get(name, name)


async def get_skills(
    config: Config,
    is_private: bool,
    **_,
) -> list[PythBaseTool]:
    """Get all enabled Pyth skills.

    Args:
        config: The configuration for Pyth skills.
        is_private: Whether to include private skills.

    Returns:
        A list of enabled Pyth skills.
    """
    tools: list[PythBaseTool] = []

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

    Pyth skills only require HTTP access to the Pyth Hermes API,
    so they are always available.
    """
    return True
