import logging
from typing import TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.dexscreener.base import DexScreenerBaseTool
from intentkit.skills.dexscreener.get_pair_info import GetPairInfo
from intentkit.skills.dexscreener.get_token_pairs import GetTokenPairs
from intentkit.skills.dexscreener.get_tokens_info import GetTokensInfo
from intentkit.skills.dexscreener.search_token import SearchToken

# Cache skills at the system level, because they are stateless
_cache: dict[str, DexScreenerBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    search_token: SkillState
    get_pair_info: SkillState
    get_token_pairs: SkillState
    get_tokens_info: SkillState


_SKILL_NAME_TO_CLASS_MAP: dict[str, type[DexScreenerBaseTool]] = {
    "search_token": SearchToken,
    "get_pair_info": GetPairInfo,
    "get_token_pairs": GetTokenPairs,
    "get_tokens_info": GetTokensInfo,
}


class Config(SkillConfig):
    """Configuration for DexScreener skills."""

    enabled: bool
    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[DexScreenerBaseTool]:
    """Get all DexScreener skills.

    Args:
        config: The configuration for DexScreener skills.
        is_private: Whether to include private skills.

    Returns:
        A list of DexScreener skills.
    """

    available_skills = []

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    logger.debug(f"Available Skills {available_skills}")
    logger.debug(f"Hardcoded Skills {_SKILL_NAME_TO_CLASS_MAP}")

    # Get each skill using the cached getter
    result = []
    for name in available_skills:
        skill = get_dexscreener_skills(name)
        if skill:
            result.append(skill)
    return result


def get_dexscreener_skills(
    name: str,
) -> DexScreenerBaseTool | None:
    """Get a DexScreener skill by name.

    Args:
        name: The name of the skill to get

    Returns:
        The requested DexScreener skill
    """

    # Return from cache immediately if already exists
    if name in _cache:
        return _cache[name]

    skill_class = _SKILL_NAME_TO_CLASS_MAP.get(name)
    if not skill_class:
        logger.warning(f"Unknown Dexscreener skill: {name}")
        return None

    _cache[name] = skill_class()
    return _cache[name]
