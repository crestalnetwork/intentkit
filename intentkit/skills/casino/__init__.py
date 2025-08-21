"""Casino skills for card games and dice rolling."""

import logging
from typing import TypedDict

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.casino.base import CasinoBaseTool
from intentkit.skills.casino.deck_draw import CasinoDeckDraw
from intentkit.skills.casino.deck_shuffle import CasinoDeckShuffle
from intentkit.skills.casino.dice_roll import CasinoDiceRoll

# Cache skills at the system level, because they are stateless
_cache: dict[str, CasinoBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    deck_shuffle: SkillState
    deck_draw: SkillState
    dice_roll: SkillState


class Config(SkillConfig):
    """Configuration for Casino skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[CasinoBaseTool]:
    """Get all Casino skills.

    Args:
        config: The configuration for Casino skills.
        is_private: Whether to include private skills.
        store: The skill store for persisting data.

    Returns:
        A list of Casino skills.
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
        skill = get_casino_skill(name, store)
        if skill:
            result.append(skill)
    return result


def get_casino_skill(
    name: str,
    store: SkillStoreABC,
) -> CasinoBaseTool:
    """Get a Casino skill by name.

    Args:
        name: The name of the skill to get
        store: The skill store for persisting data

    Returns:
        The requested Casino skill
    """
    if name == "deck_shuffle":
        if name not in _cache:
            _cache[name] = CasinoDeckShuffle(
                skill_store=store,
            )
        return _cache[name]
    elif name == "deck_draw":
        if name not in _cache:
            _cache[name] = CasinoDeckDraw(
                skill_store=store,
            )
        return _cache[name]
    elif name == "dice_roll":
        if name not in _cache:
            _cache[name] = CasinoDiceRoll(
                skill_store=store,
            )
        return _cache[name]
    else:
        raise ValueError(f"Unknown Casino skill: {name}")
