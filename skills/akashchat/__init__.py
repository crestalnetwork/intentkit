"""AkashChat skills."""

import logging
from typing import TypedDict

from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillState
from skills.akashchat.base import AkashChatBaseTool
from skills.akashchat.akashgen_image_generation import AkashGenImageGeneration

# Cache skills at the system level, because they are stateless
_cache: dict[str, AkashChatBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    akashgen_image_generation: SkillState


class Config(SkillConfig):
    """Configuration for AkashChat skills."""

    states: SkillStates
    api_key: str


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[AkashChatBaseTool]:
    """Get all AkashChat skills.

    Args:
        config: The configuration for AkashChat skills.
        is_private: Whether to include private skills.
        store: The skill store for persisting data.

    Returns:
        A list of AkashChat skills.
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
        skill = get_akashchat_skill(name, store)
        if skill:
            result.append(skill)
    return result


def get_akashchat_skill(
    name: str,
    store: SkillStoreABC,
) -> AkashChatBaseTool:
    """Get an AkashChat skill by name.

    Args:
        name: The name of the skill to get
        store: The skill store for persisting data

    Returns:
        The requested AkashChat skill
    """
    if name == "akashgen_image_generation":
        if name not in _cache:
            _cache[name] = AkashGenImageGeneration(
                skill_store=store,
            )
        return _cache[name]
    else:
        logger.warning(f"Unknown AkashChat skill: {name}")
        return None
