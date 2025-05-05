# venice_image/__init__.py

import logging
from typing import List, NotRequired, Optional, TypedDict

from abstracts.skill import SkillStoreABC
from skills.base import (
    SkillConfig,
    SkillState,
)  # Assuming SkillState is like Literal["disabled", "public", "private"]

# Import the base tool and all specific model skill classes
from skills.venice_image.base import VeniceImageBaseTool
from skills.venice_image.image_generation_fluently_xl import ImageGenerationFluentlyXL
from skills.venice_image.image_generation_flux_dev import ImageGenerationFluxDev
from skills.venice_image.image_generation_flux_dev_uncensored import (
    ImageGenerationFluxDevUncensored,
)
from skills.venice_image.image_generation_lustify_sdxl import ImageGenerationLustifySDXL
from skills.venice_image.image_generation_pony_realism import ImageGenerationPonyRealism
from skills.venice_image.image_generation_stable_diffusion_3_5 import (
    ImageGenerationStableDiffusion35,
)
from skills.venice_image.image_generation_venice_sd35 import ImageGenerationVeniceSD35

# Cache skills at the system level, because they are stateless and only depend on the store
_cache: dict[str, VeniceImageBaseTool] = {}

logger = logging.getLogger(__name__)


# Define the expected structure for the 'states' dictionary in the config
class SkillStates(TypedDict):
    image_generation_flux_dev: SkillState
    image_generation_flux_dev_uncensored: SkillState
    image_generation_venice_sd35: SkillState
    image_generation_fluently_xl: SkillState
    image_generation_lustify_sdxl: SkillState
    image_generation_pony_realism: SkillState
    image_generation_stable_diffusion_3_5: SkillState
    # Add new skill names here if more models are added


# Define the overall configuration structure for the venice_image category
class Config(SkillConfig):
    """Configuration for Venice Image skills."""

    enabled: bool  # Keep standard enabled flag
    states: SkillStates
    api_key: NotRequired[Optional[str]]  # Explicitly Optional
    safe_mode: NotRequired[bool]  # Defaults handled in base or usage
    hide_watermark: NotRequired[bool]  # Defaults handled in base or usage
    negative_prompt: NotRequired[str]  # Defaults handled in base or usage
    rate_limit_number: NotRequired[Optional[int]]  # Explicitly Optional
    rate_limit_minutes: NotRequired[Optional[int]]  # Explicitly Optional


# Map skill names to their corresponding classes for the factory function
_SKILL_NAME_TO_CLASS_MAP = {
    "image_generation_flux_dev": ImageGenerationFluxDev,
    "image_generation_flux_dev_uncensored": ImageGenerationFluxDevUncensored,
    "image_generation_venice_sd35": ImageGenerationVeniceSD35,
    "image_generation_fluently_xl": ImageGenerationFluentlyXL,
    "image_generation_lustify_sdxl": ImageGenerationLustifySDXL,
    "image_generation_pony_realism": ImageGenerationPonyRealism,
    "image_generation_stable_diffusion_3_5": ImageGenerationStableDiffusion35,
    # Add new mappings here: "skill_name": SkillClassName
}


async def get_skills(
    config: Config,  # Use the specific Config TypedDict for better type hinting
    is_private: bool,
    store: SkillStoreABC,
    **_,  # Allow for extra arguments if the loader passes them
) -> List[VeniceImageBaseTool]:
    """Get all enabled Venice Image skills based on configuration and privacy level.

    Args:
        config: The configuration for Venice Image skills.
        is_private: Whether the context is private (e.g., agent owner).
        store: The skill store for persisting data and accessing system config.

    Returns:
        A list of instantiated and enabled Venice Image skill objects.
    """
    # Check if the entire category is disabled first
    if not config.get("enabled", False):
        return []

    available_skills: List[VeniceImageBaseTool] = []
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
            skill_instance = get_venice_image_skill(skill_name, store)
            if skill_instance:
                available_skills.append(skill_instance)
            else:
                # This case should ideally not happen if the map is correct
                logger.warning(f"Could not instantiate known skill: {skill_name}")

    return available_skills


def get_venice_image_skill(
    name: str,
    store: SkillStoreABC,
) -> Optional[VeniceImageBaseTool]:
    """
    Factory function to get a cached Venice Image skill instance by name.

    Args:
        name: The name of the skill to get (must match keys in _SKILL_NAME_TO_CLASS_MAP).
        store: The skill store, passed to the skill constructor.

    Returns:
        The requested Venice Image skill instance, or None if the name is unknown.
    """
    # Check cache first
    if name in _cache:
        return _cache[name]

    # Get the class from the map
    skill_class = _SKILL_NAME_TO_CLASS_MAP.get(name)

    if skill_class:
        try:
            # Instantiate the skill and add to cache
            instance = skill_class(skill_store=store)
            _cache[name] = instance
            return instance
        except Exception as e:
            logger.error(
                f"Failed to instantiate Venice Image skill '{name}': {e}", exc_info=True
            )
            return None  # Failed to instantiate
    else:
        # This handles cases where a name might be in config but not in our map
        logger.warning(f"Attempted to get unknown Venice Image skill: {name}")
        return None
