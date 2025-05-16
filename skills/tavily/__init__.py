"""Tavily search skills."""

import logging
from typing import TypedDict

from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillState
from skills.tavily.base import TavilyBaseTool
from skills.tavily.tavily_extract import TavilyExtract
from skills.tavily.tavily_search import TavilySearch

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
    store: SkillStoreABC,
    **_,
) -> list[TavilyBaseTool]:
    """Get all Tavily search skills.

    Args:
        config: The configuration for Tavily search skills.
        is_private: Whether to include private skills.
        store: The skill store for persisting data.

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
        skill = get_tavily_skill(name, store)
        if skill:
            result.append(skill)
    return result


def get_tavily_skill(
    name: str,
    store: SkillStoreABC,
) -> TavilyBaseTool:
    """Get a Tavily search skill by name.

    Args:
        name: The name of the skill to get
        store: The skill store for persisting data

    Returns:
        The requested Tavily search skill
    """
    if name == "tavily_search":
        if name not in _cache:
            _cache[name] = TavilySearch(
                skill_store=store,
            )
        return _cache[name]
    elif name == "tavily_extract":
        if name not in _cache:
            _cache[name] = TavilyExtract(
                skill_store=store,
            )
        return _cache[name]
    else:
        logger.warning(f"Unknown Tavily skill: {name}")
        return None
