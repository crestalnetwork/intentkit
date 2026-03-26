import logging
from typing import NotRequired, TypedDict

from intentkit.config.config import config as system_config
from intentkit.skills.aixbt.base import AIXBTBaseTool
from intentkit.skills.aixbt.projects import AIXBTProjects
from intentkit.skills.base import SkillConfig, SkillState

logger = logging.getLogger(__name__)

# Cache skills at the system level, because they are stateless
_cache: dict[str, AIXBTBaseTool] = {}


class SkillStates(TypedDict):
    aixbt_projects: SkillState


class Config(SkillConfig):
    """Configuration for AIXBT API skills."""

    states: SkillStates
    rate_limit_number: NotRequired[int]
    rate_limit_minutes: NotRequired[int]


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[AIXBTBaseTool]:
    """Get all AIXBT API skills."""
    if not config.get("enabled", False):
        return []

    available_skills = []

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    # Get each skill using the cached getter
    return [s for name in available_skills if (s := get_aixbt_skill(name))]


def get_aixbt_skill(
    name: str,
) -> AIXBTBaseTool | None:
    """Get an AIXBT API skill by name."""

    if name == "aixbt_projects":
        if name not in _cache:
            _cache[name] = AIXBTProjects()
        return _cache[name]
    else:
        logger.warning("Unknown AIXBT skill: %s", name)
        return None


def available() -> bool:
    """Check if this skill category is available based on system config."""
    return bool(system_config.aixbt_api_key)
