"""System skills."""

import logging
from typing import TypedDict

from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillOwnerState
from skills.system.base import SystemBaseTool
from skills.system.get_api_key import GetApiKey
from skills.system.reset_api_key import ResetApiKey

# Cache skills at the system level, because they are stateless
_cache: dict[str, SystemBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    get_api_key: SkillOwnerState
    reset_api_key: SkillOwnerState


class Config(SkillConfig):
    """Configuration for system skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[SystemBaseTool]:
    """Get all system skills.

    Args:
        config: The configuration for system skills.
        is_private: Whether to include private skills.
        store: The skill store for persisting data.

    Returns:
        A list of system skills.
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
        skill = get_system_skill(name, store)
        if skill:
            result.append(skill)
    return result


def get_system_skill(
    name: str,
    store: SkillStoreABC,
) -> SystemBaseTool:
    """Get a system skill by name.

    Args:
        name: The name of the skill to get
        store: The skill store for persisting data

    Returns:
        The requested system skill
    """
    if name == "get_api_key":
        if name not in _cache:
            _cache[name] = GetApiKey(
                skill_store=store,
            )
        return _cache[name]
    elif name == "reset_api_key":
        if name not in _cache:
            _cache[name] = ResetApiKey(
                skill_store=store,
            )
        return _cache[name]
    else:
        logger.warning(f"Unknown system skill: {name}")
        return None
