from typing import TypedDict

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.github.base import GitHubBaseTool
from intentkit.skills.github.github_search import GitHubSearch

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
    store: SkillStoreABC,
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
    return [get_github_skill(name, store) for name in available_skills]


def get_github_skill(
    name: str,
    store: SkillStoreABC,
) -> GitHubBaseTool:
    """Get a GitHub skill by name."""
    if name == "github_search":
        if name not in _cache:
            _cache[name] = GitHubSearch(
                skill_store=store,
            )
        return _cache[name]
    else:
        raise ValueError(f"Unknown GitHub skill: {name}")
