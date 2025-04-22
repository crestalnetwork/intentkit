import logging
from typing import List, NotRequired, TypedDict

from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillState
from skills.venice_image.base import VeniceImageBaseTool
from skills.venice_image.image_generation_flux_dev import ImageGenerationFluxDev

# Cache skills at the system level, because they are stateless
_cache: dict[str, VeniceImageBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    image_generation_flux_dev: SkillState


class Config(SkillConfig):
    """Configuration for Venice Image skills."""

    states: SkillStates
    api_key: NotRequired[str]
    safe_mode: NotRequired[bool] = False
    hide_watermark: NotRequired[bool] = True
    negative_prompt: NotRequired[str] = "(worst quality: 1.4), bad quality, nsfw"
    rate_limit_number: NotRequired[int]
    rate_limit_minutes: NotRequired[int]


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> List[VeniceImageBaseTool]:
    """Get all Venice Image skills.

    Args:
        config: The configuration for Venice Image skills.
        is_private: Whether to include private skills.
        store: The skill store for persisting data.

    Returns:
        A list of Venice Image skills.
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
        skill = get_venice_image_skill(name, store)
        if skill:
            result.append(skill)
    return result


def get_venice_image_skill(
    name: str,
    store: SkillStoreABC,
) -> VeniceImageBaseTool:
    """Get a Venice Image skill by name.

    Args:
        name: The name of the skill to get
        store: The skill store for persisting data

    Returns:
        The requested Venice Image skill
    """
    if name == "image_generation_flux_dev":
        if name not in _cache:
            _cache[name] = ImageGenerationFluxDev(
                skill_store=store,
            )
        return _cache[name]
    else:
        logger.warning(f"Unknown Venice Image skill: {name}")
        return None