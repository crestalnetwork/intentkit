import logging
from typing import TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.chainlist.base import ChainlistBaseTool
from intentkit.skills.chainlist.chain_lookup import ChainLookup

logger = logging.getLogger(__name__)

# Cache skills at the system level, because they are stateless
_cache: dict[str, ChainlistBaseTool] = {}


class SkillStates(TypedDict):
    chain_lookup: SkillState


class Config(SkillConfig):
    """Configuration for chainlist skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[ChainlistBaseTool]:
    """Get all chainlist skills."""
    available_skills = []

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    # Get each skill using the cached getter
    return [s for name in available_skills if (s := get_chainlist_skill(name))]


def get_chainlist_skill(
    name: str,
) -> ChainlistBaseTool | None:
    """Get a chainlist skill by name."""
    if name == "chain_lookup":
        if name not in _cache:
            _cache[name] = ChainLookup()
        return _cache[name]
    else:
        logger.warning("Unknown chainlist skill: %s", name)
        return None


def available() -> bool:
    """Check if this skill category is available based on system config."""
    return True
