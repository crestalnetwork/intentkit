from typing import TypedDict

from abstracts.skill import SkillStoreABC
from skills.aixbt.base import AIXBTBaseTool
from skills.aixbt.projects import AIXBTProjects
from skills.base import SkillConfig, SkillState

# Cache skills at the system level, because they are stateless
_cache: dict[str, AIXBTBaseTool] = {}


class SkillStates(TypedDict):
    aixbt_projects: SkillState


class Config(SkillConfig):
    """Configuration for AIXBT API skills."""

    states: SkillStates
    enabled: bool = False
    api_key_provider: str = "agent_owner"
    api_key: str = ""
    rate_limit_number: int = 1000
    rate_limit_minutes: int = 60


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
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
    return [
        get_aixbt_skill(
            name=name,
            store=store,
            api_key=config.get("api_key", ""),
        )
        for name in available_skills
    ]


def get_aixbt_skill(
    name: str,
    store: SkillStoreABC,
    api_key: str = "",
) -> AIXBTBaseTool:
    """Get an AIXBT API skill by name."""
    cache_key = f"{name}:{api_key}"

    if name == "aixbt_projects":
        if cache_key not in _cache:
            _cache[cache_key] = AIXBTProjects(
                skill_store=store,
                api_key=api_key,
            )
        return _cache[cache_key]
    else:
        raise ValueError(f"Unknown AIXBT skill: {name}")
