"""Video generation skills across multiple providers."""

import logging
from collections.abc import Callable
from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.video.base import VideoBaseTool
from intentkit.skills.video.gemini import VeoVideo, VeoVideoFast
from intentkit.skills.video.gpt import SoraVideo, SoraVideoPro
from intentkit.skills.video.grok import GrokVideo

# Cache skills at the system level, because they are stateless
_cache: dict[str, VideoBaseTool] = {}

logger = logging.getLogger(__name__)

_SKILL_NAME_TO_CLASS: dict[str, Callable[[], VideoBaseTool]] = {
    "video_grok": GrokVideo,
    "video_sora": SoraVideo,
    "video_sora_pro": SoraVideoPro,
    "video_veo": VeoVideo,
    "video_veo_fast": VeoVideoFast,
}


class SkillStates(TypedDict):
    video_grok: SkillState
    video_sora: SkillState
    video_sora_pro: SkillState
    video_veo: SkillState
    video_veo_fast: SkillState


class Config(SkillConfig):
    """Configuration for video generation skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[VideoBaseTool]:
    """Get all video generation skills.

    Args:
        config: The configuration for video skills.
        is_private: Whether to include private skills.

    Returns:
        A list of video generation skills.
    """
    available_skills = []

    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    result = []
    for name in available_skills:
        skill = _get_video_skill(name)
        if skill:
            result.append(skill)
    return result


def _get_video_skill(name: str) -> VideoBaseTool | None:
    """Get a video skill by name with caching."""
    if name in _cache:
        return _cache[name]

    cls = _SKILL_NAME_TO_CLASS.get(name)
    if cls is None:
        logger.warning("Unknown video skill: %s", name)
        return None

    _cache[name] = cls()
    return _cache[name]


def available() -> bool:
    """Check if this skill category is available based on system config."""
    return bool(
        system_config.openai_api_key
        or system_config.google_api_key
        or system_config.xai_api_key
    )
