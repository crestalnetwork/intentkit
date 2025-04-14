from typing import TypedDict

from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillState
from skills.nation.base import NationBaseTool
from skills.nation.nft_check import NftCheck

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
    return [get_nation_skill(name, store) for name in available_skills]


def get_nation_skill(
    name: str,
    store: SkillStoreABC,
) -> NationBaseTool:
    """Get a nation skill by name."""
    if name == "nft_check":
        if name not in _cache:
            _cache[name] = NftCheck(
                skill_store=store,
            )
        return _cache[name]
    else:
        raise ValueError(f"Unknown Nation skill: {name}")
