"""Heurist AI skills."""

import logging
from typing import NotRequired, TypedDict

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.heurist.base import HeuristBaseTool
from intentkit.skills.heurist.image_generation_animagine_xl import (
    ImageGenerationAnimagineXL,
)
from intentkit.skills.heurist.image_generation_arthemy_comics import (
    ImageGenerationArthemyComics,
)
from intentkit.skills.heurist.image_generation_arthemy_real import (
    ImageGenerationArthemyReal,
)
from intentkit.skills.heurist.image_generation_braindance import (
    ImageGenerationBrainDance,
)
from intentkit.skills.heurist.image_generation_cyber_realistic_xl import (
    ImageGenerationCyberRealisticXL,
)
from intentkit.skills.heurist.image_generation_flux_1_dev import ImageGenerationFlux1Dev
from intentkit.skills.heurist.image_generation_sdxl import ImageGenerationSDXL

# Cache skills at the system level, because they are stateless
_cache: dict[str, HeuristBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    image_generation_animagine_xl: SkillState
    image_generation_arthemy_comics: SkillState
    image_generation_arthemy_real: SkillState
    image_generation_braindance: SkillState
    image_generation_cyber_realistic_xl: SkillState
    image_generation_flux_1_dev: SkillState
    image_generation_sdxl: SkillState


class Config(SkillConfig):
    """Configuration for Heurist AI skills."""

    states: SkillStates
    api_key: NotRequired[str]
    rate_limit_number: NotRequired[int]
    rate_limit_minutes: NotRequired[int]


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[HeuristBaseTool]:
    """Get all Heurist AI skills.

    Args:
        config: The configuration for Heurist AI skills.
        is_private: Whether to include private skills.
        store: The skill store for persisting data.

    Returns:
        A list of Heurist AI skills.
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
        skill = get_heurist_skill(name, store)
        if skill:
            result.append(skill)
    return result


def get_heurist_skill(
    name: str,
    store: SkillStoreABC,
) -> HeuristBaseTool:
    """Get a Heurist AI skill by name.

    Args:
        name: The name of the skill to get
        store: The skill store for persisting data

    Returns:
        The requested Heurist AI skill
    """
    if name == "image_generation_animagine_xl":
        if name not in _cache:
            _cache[name] = ImageGenerationAnimagineXL(
                skill_store=store,
            )
        return _cache[name]
    elif name == "image_generation_arthemy_comics":
        if name not in _cache:
            _cache[name] = ImageGenerationArthemyComics(
                skill_store=store,
            )
        return _cache[name]
    elif name == "image_generation_arthemy_real":
        if name not in _cache:
            _cache[name] = ImageGenerationArthemyReal(
                skill_store=store,
            )
        return _cache[name]
    elif name == "image_generation_braindance":
        if name not in _cache:
            _cache[name] = ImageGenerationBrainDance(
                skill_store=store,
            )
        return _cache[name]
    elif name == "image_generation_cyber_realistic_xl":
        if name not in _cache:
            _cache[name] = ImageGenerationCyberRealisticXL(
                skill_store=store,
            )
        return _cache[name]
    elif name == "image_generation_flux_1_dev":
        if name not in _cache:
            _cache[name] = ImageGenerationFlux1Dev(
                skill_store=store,
            )
        return _cache[name]
    elif name == "image_generation_sdxl":
        if name not in _cache:
            _cache[name] = ImageGenerationSDXL(
                skill_store=store,
            )
        return _cache[name]
    else:
        logger.warning(f"Unknown Heurist skill: {name}")
        return None
