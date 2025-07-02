from typing import TypedDict

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.cookiefun.base import CookieFunBaseTool, logger
from intentkit.skills.cookiefun.get_account_details import GetAccountDetails
from intentkit.skills.cookiefun.get_account_feed import GetAccountFeed
from intentkit.skills.cookiefun.get_account_smart_followers import (
    GetAccountSmartFollowers,
)
from intentkit.skills.cookiefun.get_sectors import GetSectors
from intentkit.skills.cookiefun.search_accounts import SearchAccounts

# Cache skills at the system level, because they are stateless
_cache: dict[str, CookieFunBaseTool] = {}


class SkillStates(TypedDict):
    """States for CookieFun skills."""

    get_sectors: SkillState
    get_account_details: SkillState
    get_account_smart_followers: SkillState
    search_accounts: SkillState
    get_account_feed: SkillState


class Config(SkillConfig):
    """Configuration for CookieFun skills."""

    states: SkillStates
    api_key: str


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[CookieFunBaseTool]:
    """Get all CookieFun skills."""
    available_skills = []

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    # Get each skill using the cached getter
    skills = [get_cookiefun_skill(name, store) for name in available_skills]
    logger.info("Returning %d CookieFun skills", len(skills))
    return skills


def get_cookiefun_skill(
    name: str,
    store: SkillStoreABC,
) -> CookieFunBaseTool:
    """Get a CookieFun skill by name."""

    if name not in _cache:
        if name == "get_sectors":
            _cache[name] = GetSectors(skill_store=store)
        elif name == "get_account_details":
            _cache[name] = GetAccountDetails(skill_store=store)
        elif name == "get_account_smart_followers":
            _cache[name] = GetAccountSmartFollowers(skill_store=store)
        elif name == "search_accounts":
            _cache[name] = SearchAccounts(skill_store=store)
        elif name == "get_account_feed":
            _cache[name] = GetAccountFeed(skill_store=store)
        else:
            logger.error("Unknown CookieFun skill: %s", name)
            raise ValueError(f"Unknown CookieFun skill: {name}")

    return _cache[name]
