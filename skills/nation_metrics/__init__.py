"""Crestal Nation skill module for IntentKit.

Loads and initializes skills for fetching Crestal Nation metrics from Dune Analytics API.
"""

import logging
from typing import Dict, List, Optional, TypedDict

from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillState

from .base import NationBaseTool

logger = logging.getLogger(__name__)

# Cache for skill instances
_skill_cache: Dict[str, NationBaseTool] = {}


class SkillStates(TypedDict):
    """Type definition for Crestal Nation skill states."""

    fetch_nation_metrics: SkillState


class Config(SkillConfig):
    """Configuration schema for Crestal Nation skills."""

    states: SkillStates
    api_key: str


async def get_skills(
    config: Config,
    is_private: bool,
    store: SkillStoreABC,
    **kwargs,
) -> List[NationBaseTool]:
    """Load Crestal Nation skills based on configuration.

    Args:
        config: Skill configuration with states and API key.
        is_private: Whether the context is private (affects skill visibility).
        store: Skill store for accessing other skills.
        **kwargs: Additional keyword arguments.

    Returns:
        List of loaded Crestal Nation skill instances.
    """
    logger.info("Loading Crestal Nation skills")
    available_skills = []

    for skill_name, state in config["states"].items():
        logger.debug("Checking skill: %s, state: %s", skill_name, state)
        if state == "disabled":
            continue
        if state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    loaded_skills = []
    for name in available_skills:
        skill = get_nation_skill(name, store)
        if skill:
            logger.info("Successfully loaded skill: %s", name)
            loaded_skills.append(skill)
        else:
            logger.warning("Failed to load skill: %s", name)

    return loaded_skills


def get_nation_skill(
    name: str,
    store: SkillStoreABC,
) -> Optional[NationBaseTool]:
    """Retrieve a Crestal Nation skill instance by name.

    Args:
        name: Name of the skill (e.g., 'fetch_nation_metrics').
        store: Skill store for accessing other skills.

    Returns:
        Crestal Nation skill instance or None if not found or import fails.
    """
    if name in _skill_cache:
        logger.debug("Retrieved cached skill: %s", name)
        return _skill_cache[name]

    try:
        if name == "fetch_nation_metrics":
            from .fetch_nation_metrics import FetchNationMetrics

            _skill_cache[name] = FetchNationMetrics(skill_store=store)
        else:
            logger.warning("Unknown Crestal Nation skill: %s", name)
            return None

        logger.debug("Cached new skill instance: %s", name)
        return _skill_cache[name]

    except ImportError as e:
        logger.error("Failed to import Crestal Nation skill %s: %s", name, e)
        return None
