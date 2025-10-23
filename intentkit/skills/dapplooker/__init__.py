"""DappLooker skills for crypto market data and analytics."""

import logging
from typing import NotRequired, TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.dapplooker.base import DappLookerBaseTool
from intentkit.skills.dapplooker.dapplooker_token_data import DappLookerTokenData

# Cache skills at the system level, because they are stateless
_cache: dict[str, DappLookerBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    dapplooker_token_data: SkillState


class Config(SkillConfig):
    """Configuration for DappLooker skills."""

    states: SkillStates
    api_key: NotRequired[str]


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[DappLookerBaseTool]:
    """Get all DappLooker skills.

    Args:
        config: The configuration for DappLooker skills.
        is_private: Whether to include private skills.

    Returns:
        A list of DappLooker skills.
    """
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
        skill = get_dapplooker_skill(name)
        if skill:
            result.append(skill)
    return result


def get_dapplooker_skill(
    name: str,
) -> DappLookerBaseTool:
    """Get a DappLooker skill by name.

    Args:
        name: The name of the skill to get

    Returns:
        The requested DappLooker skill
    """
    if name == "dapplooker_token_data":
        if name not in _cache:
            _cache[name] = DappLookerTokenData()
        return _cache[name]
    else:
        logger.warning(f"Unknown DappLooker skill: {name}")
        return None
