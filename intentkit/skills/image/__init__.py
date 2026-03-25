"""Image generation skills across multiple providers."""

import logging
from collections.abc import Callable
from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.image.base import ImageBaseTool
from intentkit.skills.image.gemini import GeminiImageFlash, GeminiImagePro
from intentkit.skills.image.gpt import GPTImageFlagship, GPTImageMini
from intentkit.skills.image.grok import GrokImage, GrokImagePro
from intentkit.skills.image.minimax import MiniMaxImage
from intentkit.skills.image.openrouter import FluxPro, Riverflow

# Cache skills at the system level, because they are stateless
_cache: dict[str, ImageBaseTool] = {}

logger = logging.getLogger(__name__)

_SKILL_NAME_TO_CLASS: dict[str, Callable[[], ImageBaseTool]] = {
    "image_gpt": GPTImageFlagship,
    "image_gpt_mini": GPTImageMini,
    "image_gemini_pro": GeminiImagePro,
    "image_gemini_flash": GeminiImageFlash,
    "image_grok_pro": GrokImagePro,
    "image_grok": GrokImage,
    "image_flux_pro": FluxPro,
    "image_riverflow": Riverflow,
    "image_minimax": MiniMaxImage,
}


class SkillStates(TypedDict):
    image_gpt: SkillState
    image_gpt_mini: SkillState
    image_gemini_pro: SkillState
    image_gemini_flash: SkillState
    image_grok_pro: SkillState
    image_grok: SkillState
    image_flux_pro: SkillState
    image_riverflow: SkillState
    image_minimax: SkillState


class Config(SkillConfig):
    """Configuration for image generation skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[ImageBaseTool]:
    """Get all image generation skills.

    Args:
        config: The configuration for image skills.
        is_private: Whether to include private skills.

    Returns:
        A list of image generation skills.
    """
    available_skills = []

    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    result = []
    for name in available_skills:
        skill = get_image_skill(name)
        if skill:
            result.append(skill)
    return result


def get_image_skill(name: str) -> ImageBaseTool | None:
    """Get an image skill by name with caching."""
    if name in _cache:
        return _cache[name]

    cls = _SKILL_NAME_TO_CLASS.get(name)
    if cls is None:
        logger.warning("Unknown image skill: %s", name)
        return None

    _cache[name] = cls()
    return _cache[name]


def available() -> bool:
    """Check if this skill category is available based on system config."""
    return bool(
        system_config.openai_api_key
        or system_config.google_api_key
        or system_config.xai_api_key
        or system_config.openrouter_api_key
        or system_config.minimax_api_key
    )
