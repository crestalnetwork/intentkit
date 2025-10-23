from typing import TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.unrealspeech.base import UnrealSpeechBaseTool
from intentkit.skills.unrealspeech.text_to_speech import TextToSpeech

# Cache skills at the system level, because they are stateless
_cache: dict[str, UnrealSpeechBaseTool] = {}


class SkillStates(TypedDict):
    text_to_speech: SkillState


class Config(SkillConfig):
    """Configuration for UnrealSpeech skills."""

    states: SkillStates
    api_key: str = ""  # Optional API key


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[UnrealSpeechBaseTool]:
    """Get all UnrealSpeech tools."""
    available_skills = []

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    # Get each skill using the cached getter
    return [get_unrealspeech_skill(name) for name in available_skills]


def get_unrealspeech_skill(
    name: str,
) -> UnrealSpeechBaseTool:
    """Get an UnrealSpeech skill by name."""
    if name == "text_to_speech":
        if name not in _cache:
            _cache[name] = TextToSpeech()
        return _cache[name]
    else:
        raise ValueError(f"Unknown UnrealSpeech skill: {name}")
