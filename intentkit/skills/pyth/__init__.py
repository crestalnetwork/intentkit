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


# Cache for stateless skills
_cache: dict[str, PythBaseTool] = {
    "pyth_fetch_price": PythFetchPrice(),
    "pyth_fetch_price_feed": PythFetchPriceFeed(),
}


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
            # Check cache first
            if skill_name in _cache:
                tools.append(_cache[skill_name])

    return tools


def available() -> bool:
    """Check if this skill category is available based on system config.

    Pyth skills only require HTTP access to the Pyth Hermes API,
    so they are always available.
    """
    return True
