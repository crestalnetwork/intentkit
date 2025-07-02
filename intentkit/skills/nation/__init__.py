import logging
from typing import Optional, TypedDict

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.nation.base import NationBaseTool
from intentkit.skills.nation.nft_check import NftCheck

logger = logging.getLogger(__name__)

# Cache skills at the system level, because they are stateless
_cache: dict[str, NationBaseTool] = {}


class SkillStates(TypedDict):
    nft_check: SkillState


class Config(SkillConfig):
    """Configuration for nation skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[NationBaseTool]:
    """Get all nation skills."""
    available_skills = []

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    # Get each skill using the cached getter
    return [
        skill
        for name in available_skills
        if (skill := get_nation_skill(name, store)) is not None
    ]


def get_nation_skill(
    name: str,
    store: SkillStoreABC,
) -> Optional[NationBaseTool]:
    """Get a nation skill by name."""
    if name == "nft_check":
        if name not in _cache:
            _cache[name] = NftCheck(
                skill_store=store,
            )
        return _cache[name]
    else:
        logger.error(f"Unknown Nation skill: {name}")
        return None
