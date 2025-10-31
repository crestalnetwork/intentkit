import logging
from typing import Literal, TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.venice_audio.base import VeniceAudioBaseTool
from intentkit.skills.venice_audio.venice_audio import VeniceAudioTool

logger = logging.getLogger(__name__)

_cache: dict[str, VeniceAudioBaseTool] = {}

_SKILL_NAME_TO_CLASS_MAP = {
    "text_to_speech": VeniceAudioTool,
    # Add new mappings here: "skill_name": SkillClassName
}


class SkillStates(TypedDict):
    text_to_speech: SkillState


class Config(SkillConfig):
    enabled: bool
    voice_model: Literal["af_heart", "bm_lewis", "custom"]
    states: SkillStates  # type: ignore
    api_key_provider: Literal["agent_owner"] | None

    # conditionally required
    api_key: str | None
    voice_model_custom: list[str] | None

    # optional
    rate_limit_number: int | None
    rate_limit_minutes: int | None


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,  # Allow for extra arguments if the loader passes them
) -> list[VeniceAudioBaseTool]:
    """
    Factory function to create and return Venice Audio skill tools.

    Args:
        config: The configuration dictionary for the Venice Audio skill.
        agent_id: The ID of the agent requesting the skills.

    Returns:
        A list of VeniceAudioBaseTool instances for the Venice Audio skill.
    """
    # Check if the entire category is disabled first
    if not config.get("enabled", False):
        return []

    available_skills: list[VeniceAudioBaseTool] = []
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
            skill_instance = get_venice_audio_skill(skill_name)
            if skill_instance:
                available_skills.append(skill_instance)
            else:
                # This case should ideally not happen if the map is correct
                logger.warning(f"Could not instantiate known skill: {skill_name}")

    return available_skills


def get_venice_audio_skill(
    name: str,
) -> VeniceAudioBaseTool | None:
    """
    Factory function to get a cached Venice Audio skill instance by name.

    Args:
        name: The name of voice model.

    Returns:
        The requested Venice Audio skill instance, or None if the name is unknown.
    """

    # Return from cache immediately if already exists
    if name in _cache:
        return _cache[name]

    # Cache and return the newly created instance
    _cache[name] = VeniceAudioTool()
    return _cache[name]
