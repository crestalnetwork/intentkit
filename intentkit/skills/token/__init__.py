"""Token skills for blockchain token analysis."""

import logging
from typing import TypedDict

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.token.base import TokenBaseTool
from intentkit.skills.token.erc20_transfers import ERC20Transfers
from intentkit.skills.token.token_analytics import TokenAnalytics
from intentkit.skills.token.token_price import TokenPrice
from intentkit.skills.token.token_search import TokenSearch

# Cache skills at the system level, because they are stateless
_cache: dict[str, TokenBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    """State configurations for Token skills."""

    token_price: SkillState
    token_erc20_transfers: SkillState
    token_search: SkillState
    token_analytics: SkillState


class Config(SkillConfig):
    """Configuration for Token blockchain analysis skills."""

    states: SkillStates
    api_key: str


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[TokenBaseTool]:
    """Get all Token blockchain analysis skills.

    Args:
        config: The configuration for Token skills.
        is_private: Whether to include private skills.
        store: The skill store for persisting data.

    Returns:
        A list of Token blockchain analysis skills.
    """
    if "states" not in config:
        logger.error("No 'states' field in config")
        return []

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
        skill = get_token_skill(name, store)
        if skill:
            result.append(skill)

    return result


def get_token_skill(
    name: str,
    store: SkillStoreABC,
) -> TokenBaseTool:
    """Get a Token blockchain analysis skill by name.

    Args:
        name: The name of the skill to get
        store: The skill store for persisting data

    Returns:
        The requested Token blockchain analysis skill
    """
    if name in _cache:
        return _cache[name]

    skill = None
    if name == "token_price":
        skill = TokenPrice(skill_store=store)
    elif name == "token_erc20_transfers":
        skill = ERC20Transfers(skill_store=store)
    elif name == "token_search":
        skill = TokenSearch(skill_store=store)
    elif name == "token_analytics":
        skill = TokenAnalytics(skill_store=store)
    else:
        logger.warning(f"Unknown Token skill: {name}")
        return None

    if skill:
        _cache[name] = skill

    return skill
