import logging
from typing import List, Literal, Optional, TypedDict

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.carv.base import CarvBaseTool
from intentkit.skills.carv.fetch_news import FetchNewsTool
from intentkit.skills.carv.onchain_query import OnchainQueryTool
from intentkit.skills.carv.token_info_and_price import TokenInfoAndPriceTool

logger = logging.getLogger(__name__)


_cache: dict[str, CarvBaseTool] = {}

_SKILL_NAME_TO_CLASS_MAP: dict[str, type[CarvBaseTool]] = {
    "onchain_query": OnchainQueryTool,
    "token_info_and_price": TokenInfoAndPriceTool,
    "fetch_news": FetchNewsTool,
}


class SkillStates(TypedDict):
    onchain_query: SkillState
    token_info_and_price: SkillState
    fetch_news: SkillState


class Config(SkillConfig):
    enabled: bool
    states: SkillStates  # type: ignore
    api_key_provider: Optional[Literal["agent_owner", "platform"]]

    # conditionally required
    api_key: Optional[str]

    # optional
    rate_limit_number: Optional[int]
    rate_limit_minutes: Optional[int]


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[CarvBaseTool]:
    """
    Factory function to create and return CARV skill tools based on the provided configuration.

    Args:
        config: The configuration object for the CARV skill.
        is_private: A boolean indicating whether the request is from a private context.
        store: An instance of `SkillStoreABC`.

    Returns:
        A list of `CarvBaseTool` instances.
    """
    # Check if the entire category is disabled first
    if not config.get("enabled", False):
        return []

    available_skills: List[CarvBaseTool] = []
    skill_states = config.get("states", {})

    # Iterate through all known skills defined in the map
    for skill_name in _SKILL_NAME_TO_CLASS_MAP:
        state = skill_states.get(
            skill_name, "disabled"
        )  # Default to disabled if not in config

        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            # If enabled, get the skill instance using the factory function
            skill_instance = get_carv_skill(skill_name, store)
            if skill_instance:
                available_skills.append(skill_instance)
            else:
                logger.warning(f"Could not instantiate known skill: {skill_name}")

    return available_skills


def get_carv_skill(
    name: str,
    store: SkillStoreABC,
) -> Optional[CarvBaseTool]:
    """
    Factory function to retrieve a cached CARV skill instance by name.

    Args:
        name: The name of the CARV skill to retrieve.
        store: An instance of `SkillStoreABC`.

    Returns:
        The requested `CarvBaseTool` instance if found and enabled, otherwise None.
    """

    # Return from cache immediately if already exists
    if name in _cache:
        return _cache[name]

    # Get the class from the map
    skill_class = _SKILL_NAME_TO_CLASS_MAP.get(name)

    if skill_class:
        try:
            # Instantiate the skill and add to cache
            instance = skill_class(skill_store=store)  # type: ignore
            _cache[name] = instance
            return instance
        except Exception as e:
            logger.error(
                f"Failed to instantiate Carv skill '{name}': {e}", exc_info=True
            )
            return None  # Failed to instantiate
    else:
        # This handles cases where a name might be in config but not in our map
        logger.warning(f"Attempted to get unknown Carv skill: {name}")
        return None
