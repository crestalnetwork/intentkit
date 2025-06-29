import logging
from typing import Optional, TypedDict

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.dexscreener.base import DexScreenerBaseTool
from intentkit.skills.dexscreener.search_token import SearchToken

# Cache skills at the system level, because they are stateless
_cache: dict[str, DexScreenerBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    search_token: SkillState


_SKILL_NAME_TO_CLASS_MAP: dict[str, type[DexScreenerBaseTool]] = {
    "search_token": SearchToken,
}


class Config(SkillConfig):
    """Configuration for DexScreener skills."""

    enabled: bool
    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[DexScreenerBaseTool]:
    """Get all DexScreener skills.

    Args:
        config: The configuration for DexScreener skills.
        is_private: Whether to include private skills.
        store: The skill store for persisting data.

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
        skill = get_dexscreener_skills(name, store)
        if skill:
            result.append(skill)
    return result


def get_dexscreener_skills(
    name: str,
    store: SkillStoreABC,
) -> Optional[DexScreenerBaseTool]:
    """Get a DexScreener skill by name.

    Args:
        name: The name of the skill to get
        store: The skill store for persisting data

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

    _cache[name] = skill_class(skill_store=store)
    return _cache[name]
