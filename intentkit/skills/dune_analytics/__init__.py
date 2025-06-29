"""Dune Analytics skill module for IntentKit.

Loads and initializes skills for fetching data from Dune Analytics API.
"""

import logging
from typing import Dict, List, Optional, TypedDict

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.dune_analytics.base import DuneBaseTool

logger = logging.getLogger(__name__)

# Cache for skill instances
_skill_cache: Dict[str, DuneBaseTool] = {}


class SkillStates(TypedDict):
    """Type definition for Dune Analytics skill states."""

    fetch_nation_metrics: SkillState
    fetch_kol_buys: SkillState


class Config(SkillConfig):
    """Configuration schema for Dune Analytics skills."""

    states: SkillStates
    api_key: str


async def get_skills(
    config: Config,
    is_private: bool,
    store: SkillStoreABC,
    **kwargs,
) -> List[DuneBaseTool]:
    """Load Dune Analytics skills based on configuration.

    Args:
        config: Skill configuration with states and API key.
        is_private: Whether the context is private (affects skill visibility).
        store: Skill store for accessing other skills.
        **kwargs: Additional keyword arguments.

    Returns:
        List of loaded Dune Analytics skill instances.
    """
    logger.info("Loading Dune Analytics skills")
    available_skills = []

    for skill_name, state in config["states"].items():
        logger.debug("Checking skill: %s, state: %s", skill_name, state)
        if state == "disabled":
            continue
        if state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    loaded_skills = []
    for name in available_skills:
        skill = get_dune_skill(name, store)
        if skill:
            logger.info("Successfully loaded skill: %s", name)
            loaded_skills.append(skill)
        else:
            logger.warning("Failed to load skill: %s", name)

    return loaded_skills


def get_dune_skill(name: str, store: SkillStoreABC) -> Optional[DuneBaseTool]:
    """Retrieve a Dune Analytics skill instance by name.

    Args:
        name: Name of the skill (e.g., 'fetch_nation_metrics', 'fetch_kol_buys').
        store: Skill store for accessing other skills.

    Returns:
        Dune Analytics skill instance or None if not found or import fails.
    """
    if name in _skill_cache:
        logger.debug("Retrieved cached skill: %s", name)
        return _skill_cache[name]

    try:
        if name == "fetch_nation_metrics":
            from .fetch_nation_metrics import FetchNationMetrics

            _skill_cache[name] = FetchNationMetrics(skill_store=store)
        elif name == "fetch_kol_buys":
            from .fetch_kol_buys import FetchKOLBuys

            _skill_cache[name] = FetchKOLBuys(skill_store=store)
        else:
            logger.warning("Unknown Dune Analytics skill: %s", name)
            return None

        logger.debug("Cached new skill instance: %s", name)
        return _skill_cache[name]
    except ImportError as e:
        logger.error("Failed to import skill %s: %s", name, e)
        return None
