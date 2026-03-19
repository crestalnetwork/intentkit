import logging
from typing import TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.github.base import GitHubBaseTool
from intentkit.skills.github.github_search import GitHubSearch

logger = logging.getLogger(__name__)

# Cache skills at the system level, because they are stateless
_cache: dict[str, GitHubBaseTool] = {}


class SkillStates(TypedDict):
    github_search: SkillState


class Config(SkillConfig):
    """Configuration for GitHub skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[GitHubBaseTool]:
    """Get all GitHub skills."""
    available_skills = []

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    # Get each skill using the cached getter
    return [s for name in available_skills if (s := get_github_skill(name))]


def get_github_skill(
    name: str,
) -> GitHubBaseTool | None:
    """Get a GitHub skill by name."""
    if name == "github_search":
        if name not in _cache:
            _cache[name] = GitHubSearch()
        return _cache[name]
    else:
        logger.warning("Unknown GitHub skill: %s", name)
        return None


def available() -> bool:
    """Check if this skill category is available based on system config."""
    return True
