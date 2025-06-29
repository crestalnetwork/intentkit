"""Allora skill module."""

import logging
from typing import NotRequired, TypedDict

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.allora.base import AlloraBaseTool
from intentkit.skills.allora.price import AlloraGetPrice
from intentkit.skills.base import SkillConfig, SkillState

# Cache skills at the system level, because they are stateless
_cache: dict[str, AlloraBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    get_price_prediction: SkillState


class Config(SkillConfig):
    """Configuration for Allora skills."""

    states: SkillStates
    api_key: NotRequired[str]


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[AlloraBaseTool]:
    """Get all Allora skills.

    Args:
        config: The configuration for Allora skills.
        is_private: Whether to include private skills.
        store: The skill store for persisting data.

    Returns:
        A list of Allora skills.
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
        skill = get_allora_skill(name, store)
        if skill:
            result.append(skill)
    return result


def get_allora_skill(
    name: str,
    store: SkillStoreABC,
) -> AlloraBaseTool:
    """Get an Allora skill by name.

    Args:
        name: The name of the skill to get
        store: The skill store for persisting data

    Returns:
        The requested Allora skill
    """
    if name == "get_price_prediction":
        if name not in _cache:
            _cache[name] = AlloraGetPrice(
                skill_store=store,
            )
        return _cache[name]
    else:
        logger.warning(f"Unknown Allora skill: {name}")
        return None
