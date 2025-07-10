"""HTTP client skills."""

import logging
from typing import TypedDict

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.http.base import HttpBaseTool
from intentkit.skills.http.get import HttpGet
from intentkit.skills.http.post import HttpPost
from intentkit.skills.http.put import HttpPut

# Cache skills at the system level, because they are stateless
_cache: dict[str, HttpBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    """Type definition for HTTP skill states."""

    http_get: SkillState
    http_post: SkillState
    http_put: SkillState


class Config(SkillConfig):
    """Configuration for HTTP client skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[HttpBaseTool]:
    """Get all HTTP client skills.

    Args:
        config: The configuration for HTTP client skills.
        is_private: Whether to include private skills.
        store: The skill store for persisting data.

    Returns:
        A list of HTTP client skills.
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
        skill = get_http_skill(name, store)
        if skill:
            result.append(skill)
    return result


def get_http_skill(
    name: str,
    store: SkillStoreABC,
) -> HttpBaseTool:
    """Get an HTTP client skill by name.

    Args:
        name: The name of the skill to get
        store: The skill store for persisting data

    Returns:
        The requested HTTP client skill
    """
    if name == "http_get":
        if name not in _cache:
            _cache[name] = HttpGet(
                skill_store=store,
            )
        return _cache[name]
    elif name == "http_post":
        if name not in _cache:
            _cache[name] = HttpPost(
                skill_store=store,
            )
        return _cache[name]
    elif name == "http_put":
        if name not in _cache:
            _cache[name] = HttpPut(
                skill_store=store,
            )
        return _cache[name]
    else:
        logger.warning(f"Unknown HTTP skill: {name}")
        return None
