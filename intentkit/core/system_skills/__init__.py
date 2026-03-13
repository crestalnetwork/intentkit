"""System skills for IntentKit agents.

These skills wrap core functionality and are available to all agents
without additional configuration.
"""

from intentkit.core.system_skills.base import SystemSkill
from intentkit.core.system_skills.call_agent import CallAgentSkill
from intentkit.core.system_skills.create_activity import CreateActivitySkill
from intentkit.core.system_skills.create_post import CreatePostSkill
from intentkit.core.system_skills.get_post import GetPostSkill
from intentkit.core.system_skills.recent_activities import RecentActivitiesSkill
from intentkit.core.system_skills.recent_posts import RecentPostsSkill
from intentkit.core.system_skills.update_memory import UpdateMemorySkill

__all__ = [
    "SystemSkill",
    "CallAgentSkill",
    "CreateActivitySkill",
    "CreatePostSkill",
    "GetPostSkill",
    "RecentActivitiesSkill",
    "RecentPostsSkill",
    "UpdateMemorySkill",
]

# Cached singleton instances
_call_agent = CallAgentSkill()
_create_activity = CreateActivitySkill()
_recent_activities = RecentActivitiesSkill()
_create_post = CreatePostSkill()
_get_post = GetPostSkill()
_recent_posts = RecentPostsSkill()
_update_memory = UpdateMemorySkill()


def get_system_skills(
    enable_activity: bool = True,
    enable_post: bool = True,
    enable_long_term_memory: bool = False,
    enable_sub_agents: bool = False,
) -> list[SystemSkill]:
    """Get system skills instances filtered by flags.

    Args:
        enable_activity: Whether to include activity skills. Defaults to True.
        enable_post: Whether to include post skills. Defaults to True.
        enable_long_term_memory: Whether to include memory skill. Defaults to False.
        enable_sub_agents: Whether to include call_agent skill. Defaults to False.
    """
    skills: list[SystemSkill] = []
    if enable_sub_agents:
        skills.append(_call_agent)
    if enable_activity:
        skills.append(_create_activity)
        skills.append(_recent_activities)
    if enable_post:
        skills.append(_create_post)
        skills.append(_get_post)
        skills.append(_recent_posts)
    if enable_long_term_memory:
        skills.append(_update_memory)
    return skills
