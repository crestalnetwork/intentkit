"""Acolyt skill module."""

import logging
from typing import NotRequired, TypedDict

from intentkit.skills.acolyt.ask import AcolytAskGpt
from intentkit.skills.acolyt.base import AcolytBaseTool
from intentkit.skills.base import SkillConfig, SkillState

# Cache skills at the system level, because they are stateless
_cache: dict[str, AcolytBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    ask_gpt: SkillState


class Config(SkillConfig):
    """Configuration for Acolyt skills."""

    states: SkillStates
    api_key: NotRequired[str]


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[AcolytBaseTool]:
    """Get all Acolyt skills.

    Args:
        config: The configuration for Acolyt skills.
        is_private: Whether to include private skills.

    Returns:
        A list of Acolyt skills.
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
        skill = get_acolyt_skill(name)
        if skill:
            result.append(skill)
    return result


def get_acolyt_skill(
    name: str,
) -> AcolytBaseTool | None:
    """Get an Acolyt skill by name.

    Args:
        name: The name of the skill to get

    Returns:
        The requested Acolyt skill
    """
    if name == "ask_gpt":
        if name not in _cache:
            _cache[name] = AcolytAskGpt()
        return _cache[name]
    else:
        logger.warning(f"Unknown Acolyt skill: {name}")
        return None
