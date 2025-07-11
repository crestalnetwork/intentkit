"""Supabase skills."""

import logging
from typing import NotRequired, TypedDict

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.supabase.base import SupabaseBaseTool
from intentkit.skills.supabase.delete_data import SupabaseDeleteData
from intentkit.skills.supabase.fetch_data import SupabaseFetchData
from intentkit.skills.supabase.insert_data import SupabaseInsertData
from intentkit.skills.supabase.invoke_function import SupabaseInvokeFunction
from intentkit.skills.supabase.update_data import SupabaseUpdateData
from intentkit.skills.supabase.upsert_data import SupabaseUpsertData

# Cache skills at the system level, because they are stateless
_cache: dict[str, SupabaseBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    fetch_data: SkillState
    insert_data: SkillState
    update_data: SkillState
    upsert_data: SkillState
    delete_data: SkillState
    invoke_function: SkillState


class Config(SkillConfig):
    """Configuration for Supabase skills."""

    states: SkillStates
    supabase_url: str
    supabase_key: str
    public_write_tables: NotRequired[str]
    public_key: NotRequired[str]


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[SupabaseBaseTool]:
    """Get all Supabase skills."""
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
        skill = get_supabase_skill(name, store)
        if skill:
            result.append(skill)
    return result


def get_supabase_skill(
    name: str,
    store: SkillStoreABC,
) -> SupabaseBaseTool:
    """Get a Supabase skill by name.

    Args:
        name: The name of the skill to get
        store: The skill store for persisting data

    Returns:
        The requested Supabase skill
    """
    if name == "fetch_data":
        if name not in _cache:
            _cache[name] = SupabaseFetchData(
                skill_store=store,
            )
        return _cache[name]
    elif name == "insert_data":
        if name not in _cache:
            _cache[name] = SupabaseInsertData(
                skill_store=store,
            )
        return _cache[name]
    elif name == "update_data":
        if name not in _cache:
            _cache[name] = SupabaseUpdateData(
                skill_store=store,
            )
        return _cache[name]
    elif name == "upsert_data":
        if name not in _cache:
            _cache[name] = SupabaseUpsertData(
                skill_store=store,
            )
        return _cache[name]
    elif name == "delete_data":
        if name not in _cache:
            _cache[name] = SupabaseDeleteData(
                skill_store=store,
            )
        return _cache[name]
    elif name == "invoke_function":
        if name not in _cache:
            _cache[name] = SupabaseInvokeFunction(
                skill_store=store,
            )
        return _cache[name]
    else:
        logger.warning(f"Unknown Supabase skill: {name}")
        return None
