"""Tavily search skills."""

import logging
from typing import TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.tavily.base import TavilyBaseTool
from intentkit.skills.tavily.tavily_extract import TavilyExtract
from intentkit.skills.tavily.tavily_search import TavilySearch

# Cache skills at the system level, because they are stateless
_cache: dict[str, TavilyBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    tavily_search: SkillState
    tavily_extract: SkillState


class Config(SkillConfig):
    """Configuration for Tavily search skills."""

    states: SkillStates
    api_key: str


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[TavilyBaseTool]:
    """Get all Tavily search skills.

    Args:
        config: The configuration for Tavily search skills.
        is_private: Whether to include private skills.

    Returns:
        A list of Tavily search skills.
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
        skill = get_tavily_skill(name)
        if skill:
            result.append(skill)
    return result


def get_tavily_skill(
    name: str,
) -> TavilyBaseTool:
    """Get a Tavily search skill by name.

    Args:
        name: The name of the skill to get

    Returns:
        The requested Tavily search skill
    """
    if name == "tavily_search":
        if name not in _cache:
            _cache[name] = TavilySearch()
        return _cache[name]
    elif name == "tavily_extract":
        if name not in _cache:
            _cache[name] = TavilyExtract()
        return _cache[name]
    else:
        logger.warning(f"Unknown Tavily skill: {name}")
        return None
