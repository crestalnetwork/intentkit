"""UI skills."""

import logging
from typing import TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.ui.ask_user import UIAskUser
from intentkit.skills.ui.base import UIBaseTool
from intentkit.skills.ui.show_card import UIShowCard

# Cache skills at the module level, because they are stateless
_cache: dict[str, UIBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    ui_show_card: SkillState
    ui_ask_user: SkillState


class Config(SkillConfig):
    """Configuration for UI skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[UIBaseTool]:
    """Get all UI skills.

    Args:
        config: The configuration for UI skills.
        is_private: Whether to include private skills.

    Returns:
        A list of UI skills.
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
        skill = get_ui_skill(name)
        if skill:
            result.append(skill)
    return result


def get_ui_skill(
    name: str,
) -> UIBaseTool | None:
    """Get a UI skill by name.

    Args:
        name: The name of the skill to get

    Returns:
        The requested UI skill
    """
    if name == "ui_show_card":
        if name not in _cache:
            _cache[name] = UIShowCard()
        return _cache[name]
    elif name == "ui_ask_user":
        if name not in _cache:
            _cache[name] = UIAskUser()
        return _cache[name]
    else:
        logger.warning(f"Unknown UI skill: {name}")
        return None


def available() -> bool:
    """Check if this skill category is available based on system config."""
    return True
