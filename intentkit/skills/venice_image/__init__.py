import logging
from typing import NotRequired, Optional, TypedDict

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import (
    SkillConfig,
    SkillState,
)

# Import the base tool and all specific model skill classes
from intentkit.skills.venice_image.base import VeniceImageBaseTool
from intentkit.skills.venice_image.image_enhance.image_enhance import ImageEnhance
from intentkit.skills.venice_image.image_generation.image_generation_fluently_xl import (
    ImageGenerationFluentlyXL,
)
from intentkit.skills.venice_image.image_generation.image_generation_flux_dev import (
    ImageGenerationFluxDev,
)
from intentkit.skills.venice_image.image_generation.image_generation_flux_dev_uncensored import (
    ImageGenerationFluxDevUncensored,
)
from intentkit.skills.venice_image.image_generation.image_generation_lustify_sdxl import (
    ImageGenerationLustifySDXL,
)
from intentkit.skills.venice_image.image_generation.image_generation_pony_realism import (
    ImageGenerationPonyRealism,
)
from intentkit.skills.venice_image.image_generation.image_generation_stable_diffusion_3_5 import (
    ImageGenerationStableDiffusion35,
)
from intentkit.skills.venice_image.image_generation.image_generation_venice_sd35 import (
    ImageGenerationVeniceSD35,
)
from intentkit.skills.venice_image.image_upscale.image_upscale import ImageUpscale
from intentkit.skills.venice_image.image_vision.image_vision import ImageVision

# Cache skills at the system level, because they are stateless and only depend on the store
_cache: dict[str, VeniceImageBaseTool] = {}

logger = logging.getLogger(__name__)


# Define the expected structure for the 'states' dictionary in the config
class SkillStates(TypedDict):
    image_upscale: SkillState
    image_enhance: SkillState
    image_vision: SkillState
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
    api_key_provider: str = "agent_owner"
    api_key: NotRequired[Optional[str]]  # Explicitly Optional
    safe_mode: NotRequired[bool]  # Defaults handled in base or usage
    hide_watermark: NotRequired[bool]  # Defaults handled in base or usage
    negative_prompt: NotRequired[str]  # Defaults handled in base or usage
    rate_limit_number: NotRequired[Optional[int]]  # Explicitly Optional
    rate_limit_minutes: NotRequired[Optional[int]]  # Explicitly Optional


_SKILL_NAME_TO_CLASS_MAP: dict[str, type[VeniceImageBaseTool]] = {
    "image_upscale": ImageUpscale,
    "image_enhance": ImageEnhance,
    "image_vision": ImageVision,
    "image_generation_flux_dev": ImageGenerationFluxDev,
    "image_generation_flux_dev_uncensored": ImageGenerationFluxDevUncensored,
    "image_generation_venice_sd35": ImageGenerationVeniceSD35,
    "image_generation_fluently_xl": ImageGenerationFluentlyXL,
    "image_generation_lustify_sdxl": ImageGenerationLustifySDXL,
    "image_generation_pony_realism": ImageGenerationPonyRealism,
    "image_generation_stable_diffusion_3_5": ImageGenerationStableDiffusion35,
}


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,  # Allow for extra arguments if the loader passes them
) -> list[VeniceImageBaseTool]:
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

    available_skills: list[VeniceImageBaseTool] = []

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    # Get each skill using the cached getter
    result = []
    for name in available_skills:
        skill = get_venice_image_skill(name, store, config)
        if skill:
            result.append(skill)
    return result


def get_venice_image_skill(
    name: str,
    store: SkillStoreABC,
    config: "Config",
) -> Optional[VeniceImageBaseTool]:
    """
    Factory function to get a cached Venice Image skill instance by name.

    Args:
        name: The name of the skill to get (must match keys in _SKILL_NAME_TO_CLASS_MAP).
        store: The skill store, passed to the skill constructor.

    Returns:
        The requested Venice Image skill instance, or None if the name is unknown.
    """

    # Return from cache immediately if already exists
    if name in _cache:
        return _cache[name]

    skill_class = _SKILL_NAME_TO_CLASS_MAP.get(name)
    if not skill_class:
        logger.warning(f"Unknown Venice skill: {name}")
        return None

    # Cache and return the newly created instance
    _cache[name] = skill_class(
        skill_store=store,
    )
    return _cache[name]
