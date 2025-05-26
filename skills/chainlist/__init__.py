from typing import TypedDict

from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillState
from skills.chainlist.base import ChainlistBaseTool
from skills.chainlist.chain_lookup import ChainLookup

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
    store: SkillStoreABC,
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
    return [get_chainlist_skill(name, store) for name in available_skills]


def get_chainlist_skill(
    name: str,
    store: SkillStoreABC,
) -> ChainlistBaseTool:
    """Get a chainlist skill by name."""
    if name == "chain_lookup":
        if name not in _cache:
            _cache[name] = ChainLookup(
                skill_store=store,
            )
        return _cache[name]
    else:
        raise ValueError(f"Unknown chainlist skill: {name}")
