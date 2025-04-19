"""TokenMetrics skill module for IntentKit.

Provides skills to fetch price and quantitative metrics for BTC and ETH from the
TokenMetrics API.
"""

import logging
from typing import NotRequired, TypedDict

from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillState

from .base import TokenMetricsBaseTool

logger = logging.getLogger(__name__)

_cache: dict[str, TokenMetricsBaseTool] = {}


class SkillStates(TypedDict):
    """Type definition for skill states."""

    fetch_price: SkillState
    fetch_quant_data: SkillState


class Config(SkillConfig):
    """Configuration for TokenMetrics skills."""

    states: SkillStates
    api_key: NotRequired[str]


async def get_skills(
    config: Config,
    is_private: bool,
    store: SkillStoreABC,
    **kwargs,
) -> list[TokenMetricsBaseTool]:
    """Load available TokenMetrics skills based on configuration.

    Args:
        config: Skill configuration.
        is_private: Whether the context is private.
        store: Skill store for accessing other skills.
        **kwargs: Additional keyword arguments.

    Returns:
        List of loaded TokenMetrics skills.
    """
    logger.info("Loading tokenmetrics skills")
    available_skills = []

    for skill_name, state in config["states"].items():
        logger.debug(f"Checking skill: {skill_name}, state: {state}")
        if state == "disabled":
            continue
        if state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    result = []
    for name in available_skills:
        skill = get_tokenmetrics_skill(name, store)
        if skill:
            logger.info(f"Loaded skill: {name}")
            result.append(skill)
    return result


def get_tokenmetrics_skill(
    name: str,
    store: SkillStoreABC,
) -> TokenMetricsBaseTool | None:
    """Retrieve a TokenMetrics skill instance by name.

    Args:
        name: Name of the skill (e.g., 'fetch_price').
        store: Skill store for accessing other skills.

    Returns:
        TokenMetrics skill instance or None if not found.
    """
    if name == "fetch_price":
        if name not in _cache:
            from .fetch_price import FetchPrice

            _cache[name] = FetchPrice(skill_store=store)
        return _cache[name]
    if name == "fetch_quant_data":
        if name not in _cache:
            from .fetch_quant_data import FetchQuantData

            _cache[name] = FetchQuantData(skill_store=store)
        return _cache[name]
    logger.warning(f"Unknown skill: {name}")
    return None
